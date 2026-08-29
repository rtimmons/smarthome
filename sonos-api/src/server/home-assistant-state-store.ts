import {
  HomeAssistantClientLike,
  HomeAssistantEntityState,
  HomeAssistantStateChangedEvent,
  HomeAssistantStateSubscription,
} from './home-assistant-client';
import {SonosBackendError, SonosStateSnapshot} from './sonos-contract';
import {SONOS_ENTITY_IDS} from './sonos-room-map';

export interface HomeAssistantStateStoreOptions {
  client: Pick<HomeAssistantClientLike, 'getStates' | 'connectStateEvents'>;
  entityIds?: readonly string[];
  staleAfterMs?: number;
  reconnectInitialMs?: number;
  reconnectMaxMs?: number;
  now?: () => number;
  setTimeout?: typeof setTimeout;
  clearTimeout?: typeof clearTimeout;
}

export type SonosStateListener = (snapshot: SonosStateSnapshot) => void;

const DEFAULT_STALE_AFTER_MS = 30_000;
const DEFAULT_RECONNECT_INITIAL_MS = 500;
const DEFAULT_RECONNECT_MAX_MS = 10_000;

const stateTimestamp = (state: HomeAssistantEntityState): number => {
  const parsed = Date.parse(state.last_updated);
  return Number.isFinite(parsed) ? parsed : 0;
};

const safeMessage = (error: unknown): string => {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return 'Home Assistant state connection failed';
};

export class HomeAssistantStateStore {
  private readonly client: HomeAssistantStateStoreOptions['client'];
  private readonly entityIds: ReadonlySet<string>;
  private readonly staleAfterMs: number;
  private readonly reconnectInitialMs: number;
  private readonly reconnectMaxMs: number;
  private readonly now: () => number;
  private readonly setTimer: typeof setTimeout;
  private readonly clearTimer: typeof clearTimeout;
  private readonly entities = new Map<string, HomeAssistantEntityState>();
  private readonly listeners = new Set<SonosStateListener>();
  private readonly eventGenerationByEntity = new Map<string, number>();

  private subscription: HomeAssistantStateSubscription | null = null;
  private activeAttemptController: AbortController | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectDelayMs: number;
  private generation = 0;
  private started = false;
  private stopped = false;
  private connecting = false;
  private connected = false;
  private hasSnapshot = false;
  private lastObservedAt: number | null = null;
  private disconnectedAt: number | null = null;
  private lastError: string | undefined;

  constructor(options: HomeAssistantStateStoreOptions) {
    this.client = options.client;
    this.entityIds = new Set(options.entityIds || SONOS_ENTITY_IDS);
    this.staleAfterMs = options.staleAfterMs ?? DEFAULT_STALE_AFTER_MS;
    this.reconnectInitialMs =
      options.reconnectInitialMs ?? DEFAULT_RECONNECT_INITIAL_MS;
    this.reconnectMaxMs = options.reconnectMaxMs ?? DEFAULT_RECONNECT_MAX_MS;
    this.reconnectDelayMs = this.reconnectInitialMs;
    this.now = options.now || Date.now;
    this.setTimer = options.setTimeout || setTimeout;
    this.clearTimer = options.clearTimeout || clearTimeout;
  }

  async start(): Promise<void> {
    if (this.started && !this.stopped) {
      return;
    }
    this.started = true;
    this.stopped = false;
    await this.connectAndSnapshot();
  }

  stop(): void {
    if (this.stopped) {
      return;
    }
    this.stopped = true;
    this.connected = false;
    this.connecting = false;
    this.generation += 1;
    if (this.activeAttemptController) {
      this.activeAttemptController.abort();
      this.activeAttemptController = null;
    }
    if (this.reconnectTimer) {
      this.clearTimer(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.subscription) {
      this.subscription.close();
      this.subscription = null;
    }
    this.emit();
  }

  subscribe(listener: SonosStateListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  snapshot(): SonosStateSnapshot {
    const now = this.now();
    let freshness: SonosStateSnapshot['freshness'] = 'unknown';
    let ageMs = Number.MAX_SAFE_INTEGER;

    if (this.connected && this.hasSnapshot) {
      freshness = 'live';
      ageMs = 0;
    } else if (this.hasSnapshot && this.disconnectedAt !== null) {
      ageMs = Math.max(0, now - this.disconnectedAt);
      freshness = ageMs < this.staleAfterMs ? 'stale' : 'unknown';
    }

    return {
      freshness,
      connected: this.connected,
      observedAt: this.lastObservedAt,
      ageMs,
      entities: new Map(this.entities),
      ...(this.lastError ? {lastError: this.lastError} : {}),
    };
  }

  getEntity(entityId: string): HomeAssistantEntityState | undefined {
    return this.entities.get(entityId);
  }

  assertCommandable(entityIds: readonly string[]): void {
    const snapshot = this.snapshot();
    if (snapshot.freshness !== 'live') {
      throw new SonosBackendError(
        'state_unavailable',
        'Home Assistant Sonos state is not fresh enough for this action',
        503,
        true
      );
    }

    for (const entityId of entityIds) {
      if (!this.entityIds.has(entityId)) {
        throw new SonosBackendError(
          'unknown_room',
          `Unknown Sonos entity ${entityId}`,
          404
        );
      }
      const state = this.entities.get(entityId);
      if (!state || state.state === 'unavailable' || state.state === 'unknown') {
        throw new SonosBackendError(
          'room_unavailable',
          `Sonos entity ${entityId} is unavailable`,
          503,
          true
        );
      }
    }
  }

  private async connectAndSnapshot(): Promise<void> {
    if (this.stopped || this.connecting) {
      return;
    }
    this.connecting = true;
    const generation = ++this.generation;
    const attemptController = new AbortController();
    this.activeAttemptController = attemptController;
    let subscription: HomeAssistantStateSubscription | null = null;

    try {
      subscription = await this.client.connectStateEvents({
        onStateChanged: event => this.applyEvent(event, generation),
        onDisconnect: error => this.handleDisconnect(generation, error),
        onProtocolError: error => {
          if (generation === this.generation) {
            this.lastError = safeMessage(error);
            this.emit();
          }
        },
      }, attemptController.signal);

      if (this.stopped || generation !== this.generation) {
        subscription.close();
        return;
      }
      this.subscription = subscription;
      const states = await this.client.getStates(attemptController.signal);
      if (this.stopped || generation !== this.generation) {
        subscription.close();
        return;
      }

      const snapshotIds = new Set<string>();
      for (const state of states) {
        if (!this.entityIds.has(state.entity_id)) {
          continue;
        }
        snapshotIds.add(state.entity_id);
        if (this.eventGenerationByEntity.get(state.entity_id) !== generation) {
          this.applyState(state.entity_id, state);
        }
      }
      for (const entityId of this.entityIds) {
        if (
          !snapshotIds.has(entityId) &&
          this.eventGenerationByEntity.get(entityId) !== generation
        ) {
          this.entities.delete(entityId);
        }
      }

      this.hasSnapshot = true;
      this.connected = true;
      this.disconnectedAt = null;
      this.lastObservedAt = this.now();
      this.lastError = undefined;
      this.reconnectDelayMs = this.reconnectInitialMs;
      this.emit();
    } catch (error) {
      if (subscription) {
        subscription.close();
        if (this.subscription === subscription) {
          this.subscription = null;
        }
      }
      if (generation === this.generation && !this.stopped) {
        this.lastError = safeMessage(error);
        this.markDisconnected();
        this.scheduleReconnect();
      }
    } finally {
      if (this.activeAttemptController === attemptController) {
        this.activeAttemptController = null;
      }
      if (generation === this.generation) {
        this.connecting = false;
      }
    }
  }

  private applyEvent(
    event: HomeAssistantStateChangedEvent,
    generation: number
  ): void {
    if (this.stopped || generation !== this.generation || !this.entityIds.has(event.entityId)) {
      return;
    }
    this.eventGenerationByEntity.set(event.entityId, generation);
    if (event.newState) {
      this.applyState(event.entityId, event.newState);
    } else {
      this.entities.delete(event.entityId);
    }
    this.lastObservedAt = this.now();
    this.emit();
  }

  private applyState(entityId: string, next: HomeAssistantEntityState): void {
    const current = this.entities.get(entityId);
    if (current && stateTimestamp(next) <= stateTimestamp(current)) {
      return;
    }
    this.entities.set(entityId, next);
  }

  private handleDisconnect(generation: number, error?: Error): void {
    if (this.stopped || generation !== this.generation) {
      return;
    }
    this.generation += 1;
    if (this.activeAttemptController) {
      this.activeAttemptController.abort();
      this.activeAttemptController = null;
    }
    this.subscription = null;
    this.connecting = false;
    if (error) {
      this.lastError = safeMessage(error);
    }
    this.markDisconnected();
    this.scheduleReconnect();
  }

  private markDisconnected(): void {
    if (this.connected || this.disconnectedAt === null) {
      this.disconnectedAt = this.now();
    }
    this.connected = false;
    this.emit();
  }

  private scheduleReconnect(): void {
    if (this.stopped || this.reconnectTimer) {
      return;
    }
    const delay = this.reconnectDelayMs;
    this.reconnectDelayMs = Math.min(
      this.reconnectMaxMs,
      Math.max(this.reconnectInitialMs, delay * 2)
    );
    this.reconnectTimer = this.setTimer(() => {
      this.reconnectTimer = null;
      void this.connectAndSnapshot();
    }, delay);
  }

  private emit(): void {
    if (this.listeners.size === 0) {
      return;
    }
    const snapshot = this.snapshot();
    for (const listener of this.listeners) {
      listener(snapshot);
    }
  }
}
