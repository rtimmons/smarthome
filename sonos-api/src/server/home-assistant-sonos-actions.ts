import {
  HomeAssistantClientError,
  HomeAssistantClientLike,
} from './home-assistant-client';
import {SonosBackendError, SonosStateSnapshot} from './sonos-contract';
import {HomeAssistantStateStore} from './home-assistant-state-store';
import {
  EnqueuedSonosOperation,
  SonosOperationQueue,
  SonosOperationRunResult,
} from './sonos-operation-queue';
import {
  isSonosRoomName,
  roomForSonosEntity,
  SONOS_ROOM_TO_ENTITY,
  SonosRoomName,
} from './sonos-room-map';

export interface SonosActionStateStore {
  snapshot(): SonosStateSnapshot;
  assertCommandable(entityIds: readonly string[]): void;
  subscribe(listener: (snapshot: SonosStateSnapshot) => void): () => void;
}

export interface HomeAssistantSonosActionsOptions {
  client: Pick<HomeAssistantClientLike, 'callService'>;
  stateStore: SonosActionStateStore;
  operationQueue?: SonosOperationQueue;
  topologyDeadlineMs?: number;
  now?: () => number;
  setTimeout?: typeof setTimeout;
  clearTimeout?: typeof clearTimeout;
}

type MediaPlayerService =
  | 'media_play'
  | 'media_pause'
  | 'media_play_pause'
  | 'media_next_track'
  | 'select_source'
  | 'join'
  | 'unjoin'
  | 'volume_set';

interface RoomGroup {
  coordinator: SonosRoomName;
  members: SonosRoomName[];
}

const DEFAULT_TOPOLOGY_DEADLINE_MS = 45_000;
const JOIN_ALL_OBSERVATION_WINDOW_MS = 5_000;

const parseGroup = (
  snapshot: SonosStateSnapshot,
  roomName: SonosRoomName
): RoomGroup => {
  const entityId = SONOS_ROOM_TO_ENTITY[roomName];
  const state = snapshot.entities.get(entityId);
  if (!state || state.state === 'unavailable' || state.state === 'unknown') {
    throw new SonosBackendError(
      'room_unavailable',
      `Sonos room ${roomName} is unavailable`,
      503,
      true
    );
  }
  const rawMembers = state.attributes.group_members;
  if (!Array.isArray(rawMembers) || rawMembers.length === 0) {
    throw new SonosBackendError(
      'invalid_topology',
      `Sonos room ${roomName} has no authoritative group membership`,
      503,
      true
    );
  }
  const rooms = rawMembers.map(entity => {
    if (typeof entity !== 'string') {
      throw new SonosBackendError('invalid_topology', 'Sonos group membership is malformed', 502);
    }
    const room = roomForSonosEntity(entity);
    if (!room) {
      throw new SonosBackendError(
        'invalid_topology',
        `Sonos group contains unknown entity ${entity}`,
        502
      );
    }
    return room;
  });
  if (new Set(rooms).size !== rooms.length || !rooms.includes(roomName)) {
    throw new SonosBackendError('invalid_topology', 'Sonos group membership is inconsistent', 502);
  }
  return {coordinator: rooms[0], members: rooms};
};

const clampVolume = (value: number): number => Math.max(0, Math.min(100, Math.round(value)));

const volumeForRoom = (snapshot: SonosStateSnapshot, roomName: SonosRoomName): number => {
  const state = snapshot.entities.get(SONOS_ROOM_TO_ENTITY[roomName]);
  const volume = Number(state?.attributes.volume_level);
  if (!Number.isFinite(volume)) {
    throw new SonosBackendError(
      'volume_unavailable',
      `Volume is unavailable for ${roomName}`,
      503,
      true
    );
  }
  return clampVolume(volume * 100);
};

const uniqueRooms = (rooms: readonly SonosRoomName[]): SonosRoomName[] => {
  return [...new Set(rooms)];
};

const isIsolatedRoomJoinFailure = (error: unknown): boolean => {
  if (error instanceof SonosBackendError) {
    return error.code === 'room_unavailable';
  }
  if (!(error instanceof HomeAssistantClientError)) {
    return false;
  }
  return error.code === 'network' || error.code === 'timeout' ||
    (error.code === 'http' && (error.statusCode || 0) >= 500);
};

const isDefiniteRoomJoinFailure = (error: unknown): boolean => {
  return error instanceof SonosBackendError ||
    (error instanceof HomeAssistantClientError && error.code === 'http');
};

export class HomeAssistantSonosActions {
  readonly operationQueue: SonosOperationQueue;

  private readonly client: HomeAssistantSonosActionsOptions['client'];
  private readonly stateStore: SonosActionStateStore;
  private readonly topologyDeadlineMs: number;
  private readonly setTimer: typeof setTimeout;
  private readonly clearTimer: typeof clearTimeout;

  constructor(options: HomeAssistantSonosActionsOptions) {
    this.client = options.client;
    this.stateStore = options.stateStore;
    this.topologyDeadlineMs =
      options.topologyDeadlineMs ?? DEFAULT_TOPOLOGY_DEADLINE_MS;
    this.setTimer = options.setTimeout || setTimeout;
    this.clearTimer = options.clearTimeout || clearTimeout;
    this.operationQueue = options.operationQueue || new SonosOperationQueue({
      now: options.now,
      operationDeadlineMs: this.topologyDeadlineMs,
      setTimeout: this.setTimer,
      clearTimeout: this.clearTimer,
    });
  }

  play(roomName: SonosRoomName): Promise<void> {
    return this.callRoomService(roomName, 'media_play');
  }

  pause(roomName: SonosRoomName): Promise<void> {
    return this.callRoomService(roomName, 'media_pause');
  }

  playPause(roomName: SonosRoomName): Promise<void> {
    return this.callRoomService(roomName, 'media_play_pause');
  }

  next(roomName: SonosRoomName): Promise<void> {
    return this.callRoomService(roomName, 'media_next_track');
  }

  async favorite(roomName: SonosRoomName, favoriteName: string): Promise<void> {
    const entityId = SONOS_ROOM_TO_ENTITY[roomName];
    this.stateStore.assertCommandable([entityId]);
    const state = this.stateStore.snapshot().entities.get(entityId);
    const sources = state?.attributes.source_list;
    if (
      !favoriteName ||
      !Array.isArray(sources) ||
      !sources.some(source => source === favoriteName)
    ) {
      throw new SonosBackendError(
        'unknown_favorite',
        `Favorite ${favoriteName || '(empty)'} is not available for ${roomName}`,
        400
      );
    }
    await this.call('select_source', {entity_id: entityId, source: favoriteName});
  }

  join(roomName: SonosRoomName, targetRoom: SonosRoomName): EnqueuedSonosOperation {
    this.validateRooms([roomName, targetRoom]);
    this.stateStore.assertCommandable([
      SONOS_ROOM_TO_ENTITY[roomName],
      SONOS_ROOM_TO_ENTITY[targetRoom],
    ]);
    return this.operationQueue.enqueue({
      kind: 'join',
      key: `join:${roomName}:${targetRoom}`,
      targetRoom,
      requestedRooms: [roomName, targetRoom],
      run: async context => {
        const snapshot = this.stateStore.snapshot();
        const targetGroup = parseGroup(snapshot, targetRoom);
        if (targetGroup.members.includes(roomName)) {
          return;
        }
        const coordinatorEntity = SONOS_ROOM_TO_ENTITY[targetGroup.coordinator];
        const roomEntity = SONOS_ROOM_TO_ENTITY[roomName];
        this.stateStore.assertCommandable([roomEntity, coordinatorEntity]);
        await this.callTopologyAndObserve(
          'join',
          {entity_id: coordinatorEntity, group_members: [roomEntity]},
          next => {
            const observed = parseGroup(next, targetRoom);
            return observed.coordinator === targetGroup.coordinator &&
              observed.members.includes(roomName);
          },
          context.isObsolete,
          context.remainingMs,
          context.recordServiceCall,
          context.onObsolete
        );
      },
    });
  }

  leave(roomName: SonosRoomName): EnqueuedSonosOperation {
    this.validateRooms([roomName]);
    this.stateStore.assertCommandable([SONOS_ROOM_TO_ENTITY[roomName]]);
    return this.operationQueue.enqueue({
      kind: 'leave',
      key: `leave:${roomName}`,
      requestedRooms: [roomName],
      run: async context => {
        const snapshot = this.stateStore.snapshot();
        const group = parseGroup(snapshot, roomName);
        if (group.members.length === 1) {
          return;
        }
        const entityId = SONOS_ROOM_TO_ENTITY[roomName];
        this.stateStore.assertCommandable([entityId]);
        await this.callTopologyAndObserve(
          'unjoin',
          {entity_id: entityId},
          next => {
            const observed = parseGroup(next, roomName);
            return observed.coordinator === roomName &&
              observed.members.length === 1 &&
              observed.members[0] === roomName;
          },
          context.isObsolete,
          context.remainingMs,
          context.recordServiceCall,
          context.onObsolete
        );
      },
    });
  }

  joinAll(
    targetRoom: SonosRoomName,
    requestedRooms: readonly SonosRoomName[]
  ): EnqueuedSonosOperation {
    this.validateRooms([targetRoom, ...requestedRooms]);
    if (requestedRooms.length === 0) {
      throw new SonosBackendError('invalid_request', 'roomNames must not be empty', 400);
    }
    if (uniqueRooms(requestedRooms).length !== requestedRooms.length) {
      throw new SonosBackendError('invalid_request', 'roomNames must not contain duplicates', 400);
    }
    if (!requestedRooms.includes(targetRoom)) {
      throw new SonosBackendError(
        'invalid_request',
        'targetRoom must be included in roomNames',
        400
      );
    }
    const rooms = [...requestedRooms];
    const initial = this.stateStore.snapshot();
    this.stateStore.assertCommandable([SONOS_ROOM_TO_ENTITY[targetRoom]]);
    const unavailableRooms = rooms.filter(roomName => {
      const state = initial.entities.get(SONOS_ROOM_TO_ENTITY[roomName]);
      return !state || state.state === 'unavailable' || state.state === 'unknown';
    });
    const availableRooms = rooms.filter(roomName => !unavailableRooms.includes(roomName));
    const key = `join_all:${targetRoom}:${[...rooms].sort().join('|')}`;

    return this.operationQueue.enqueue({
      kind: 'join_all',
      key,
      targetRoom,
      requestedRooms: rooms,
      unavailableRooms,
      run: async context => {
        const snapshot = this.stateStore.snapshot();
        let targetGroup = parseGroup(snapshot, targetRoom);
        const currentAvailable = availableRooms.filter(roomName => {
          const state = snapshot.entities.get(SONOS_ROOM_TO_ENTITY[roomName]);
          return state && state.state !== 'unavailable' && state.state !== 'unknown';
        });
        const newlyUnavailable = rooms.filter(roomName => !currentAvailable.includes(roomName));
        if (newlyUnavailable.includes(targetRoom)) {
          throw new SonosBackendError(
            'room_unavailable',
            `Join-all target ${targetRoom} is unavailable`,
            503,
            true
          );
        }
        const targetEntity = SONOS_ROOM_TO_ENTITY[targetRoom];
        const memberRooms = currentAvailable.filter(roomName => roomName !== targetRoom);

        if (targetGroup.coordinator !== targetRoom) {
          this.stateStore.assertCommandable([targetEntity]);
          await this.callTopologyAndObserve(
            'unjoin',
            {entity_id: targetEntity},
            next => {
              const observed = parseGroup(next, targetRoom);
              return observed.coordinator === targetRoom &&
                observed.members.length === 1;
            },
            context.isObsolete,
            context.remainingMs,
            context.recordServiceCall,
            context.onObsolete
          );
          if (context.isObsolete()) {
            return;
          }
          targetGroup = parseGroup(this.stateStore.snapshot(), targetRoom);
        }

        const definiteFailures = new Set<SonosRoomName>();
        for (const memberRoom of memberRooms) {
          if (context.isObsolete()) {
            return;
          }
          this.stateStore.assertCommandable([targetEntity]);
          targetGroup = parseGroup(this.stateStore.snapshot(), targetRoom);
          if (targetGroup.coordinator !== targetRoom) {
            throw new SonosBackendError(
              'invalid_topology',
              `Join-all target ${targetRoom} is no longer the coordinator`,
              503,
              true
            );
          }
          if (targetGroup.members.includes(memberRoom)) {
            continue;
          }

          try {
            const memberEntity = SONOS_ROOM_TO_ENTITY[memberRoom];
            this.stateStore.assertCommandable([memberEntity]);
            context.recordServiceCall();
            await this.call('join', {
              entity_id: targetEntity,
              group_members: [memberEntity],
            });
          } catch (error) {
            if (context.isObsolete()) {
              return;
            }
            if (!isIsolatedRoomJoinFailure(error)) {
              throw error;
            }
            if (isDefiniteRoomJoinFailure(error)) {
              definiteFailures.add(memberRoom);
            }
          }
        }

        if (context.isObsolete()) {
          return;
        }
        const expectedJoinedRooms = currentAvailable.filter(
          roomName => !definiteFailures.has(roomName)
        );
        try {
          await this.waitForTopology(
            next => {
              const observed = parseGroup(next, targetRoom);
              return observed.coordinator === targetRoom &&
                expectedJoinedRooms.every(roomName => observed.members.includes(roomName));
            },
            Math.min(context.remainingMs(), JOIN_ALL_OBSERVATION_WINDOW_MS),
            context.isObsolete,
            context.onObsolete
          );
        } catch (error) {
          if (context.isObsolete()) {
            return;
          }
          if (!(error instanceof SonosBackendError && error.code === 'operation_timeout')) {
            throw error;
          }
        }

        const observed = parseGroup(this.stateStore.snapshot(), targetRoom);
        const failedRooms = rooms.filter(roomName =>
          newlyUnavailable.includes(roomName) ||
          definiteFailures.has(roomName) ||
          !observed.members.includes(roomName)
        );
        return {
          status: failedRooms.length > 0 ? 'partial' : 'completed',
          unavailableRooms: failedRooms,
        } satisfies SonosOperationRunResult;
      },
    });
  }

  async groupVolume(roomName: SonosRoomName, value: string | number): Promise<void> {
    this.validateRooms([roomName]);
    const snapshot = this.stateStore.snapshot();
    const group = parseGroup(snapshot, roomName);
    const entityIds = group.members.map(member => SONOS_ROOM_TO_ENTITY[member]);
    this.stateStore.assertCommandable(entityIds);

    const text = String(value).trim();
    const relative = /^[+-]/.test(text);
    const parsed = Number(text);
    if (!Number.isFinite(parsed)) {
      throw new SonosBackendError('invalid_volume', `Invalid volume ${text}`, 400);
    }
    const memberVolumes = group.members.map(roomName => ({
      roomName,
      volume: volumeForRoom(snapshot, roomName),
    }));
    const observedGroupVolume = clampVolume(
      memberVolumes.reduce((sum, member) => sum + member.volume, 0) /
      memberVolumes.length
    );
    const desired = clampVolume(relative ? observedGroupVolume + parsed : parsed);
    const updates = memberVolumes.map(member => {
      let volume: number;
      if (relative && parsed >= 0) {
        volume = member.volume + parsed;
      } else if (desired < 1) {
        volume = 0;
      } else if (desired < observedGroupVolume) {
        volume = Math.ceil(member.volume / observedGroupVolume * desired);
      } else {
        volume = member.volume + (desired - observedGroupVolume);
      }
      return {roomName: member.roomName, volume: clampVolume(volume)};
    });
    await this.setVolumes(updates);
  }

  async normalizeGroupVolume(roomName: SonosRoomName): Promise<void> {
    this.validateRooms([roomName]);
    const snapshot = this.stateStore.snapshot();
    const group = parseGroup(snapshot, roomName);
    const entityIds = group.members.map(member => SONOS_ROOM_TO_ENTITY[member]);
    this.stateStore.assertCommandable(entityIds);
    const target = volumeForRoom(snapshot, roomName);
    const updates = group.members
      .filter(member => volumeForRoom(snapshot, member) !== target)
      .map(member => ({roomName: member, volume: target}));
    await this.setVolumes(updates);
  }

  async setRoomVolume(roomName: SonosRoomName, volume: number): Promise<void> {
    this.validateRooms([roomName]);
    if (!Number.isFinite(volume)) {
      throw new SonosBackendError('invalid_volume', 'Volume must be a number', 400);
    }
    const entityId = SONOS_ROOM_TO_ENTITY[roomName];
    this.stateStore.assertCommandable([entityId]);
    await this.call('volume_set', {
      entity_id: entityId,
      volume_level: clampVolume(volume) / 100,
    });
  }

  private async callRoomService(
    roomName: SonosRoomName,
    service: Extract<MediaPlayerService,
      'media_play' | 'media_pause' | 'media_play_pause' | 'media_next_track'>
  ): Promise<void> {
    this.validateRooms([roomName]);
    const entityId = SONOS_ROOM_TO_ENTITY[roomName];
    this.stateStore.assertCommandable([entityId]);
    await this.call(service, {entity_id: entityId});
  }

  private async call(
    service: MediaPlayerService,
    data: Record<string, unknown>
  ): Promise<void> {
    await this.client.callService('media_player', service, data);
  }

  private async setVolumes(
    updates: Array<{roomName: SonosRoomName; volume: number}>
  ): Promise<void> {
    const results = await Promise.allSettled(updates.map(update => this.call('volume_set', {
      entity_id: SONOS_ROOM_TO_ENTITY[update.roomName],
      volume_level: update.volume / 100,
    })));
    const failedRooms = updates
      .filter((_update, index) => results[index].status === 'rejected')
      .map(update => update.roomName);
    if (failedRooms.length > 0) {
      const currentSnapshot = this.stateStore.snapshot();
      const observedVolumes = updates.map(update => {
        const state = currentSnapshot.entities.get(SONOS_ROOM_TO_ENTITY[update.roomName]);
        const level = Number(state?.attributes.volume_level);
        const observed = Number.isFinite(level) ? `${clampVolume(level * 100)}` : 'unknown';
        return `${update.roomName}=${observed}`;
      });
      throw new SonosBackendError(
        'volume_partial_failure',
        `Volume update failed for ${failedRooms.join(', ')}; ` +
        `current observed volumes: ${observedVolumes.join(', ')}`,
        502,
        true
      );
    }
  }

  private async callTopologyAndObserve(
    service: Extract<MediaPlayerService, 'join' | 'unjoin'>,
    data: Record<string, unknown>,
    predicate: (snapshot: SonosStateSnapshot) => boolean,
    isObsolete: () => boolean,
    remainingMs: () => number,
    recordServiceCall: () => void,
    onObsolete: (listener: () => void) => () => void
  ): Promise<void> {
    let uncertainError: Error | null = null;
    try {
      recordServiceCall();
      await this.call(service, data);
    } catch (error) {
      if (
        error instanceof HomeAssistantClientError &&
        (error.code === 'timeout' || error.code === 'network')
      ) {
        uncertainError = error;
      } else {
        throw error;
      }
    }

    if (isObsolete()) {
      return;
    }
    try {
      await this.waitForTopology(predicate, remainingMs(), isObsolete, onObsolete);
    } catch (error) {
      if (uncertainError) {
        throw new SonosBackendError(
          'operation_timeout',
          uncertainError.message,
          504,
          true
        );
      }
      throw error;
    }
  }

  private waitForTopology(
    predicate: (snapshot: SonosStateSnapshot) => boolean,
    deadlineMs: number,
    isObsolete: () => boolean,
    onObsolete: (listener: () => void) => () => void
  ): Promise<void> {
    if (isObsolete()) {
      return Promise.resolve();
    }
    try {
      if (predicate(this.stateStore.snapshot())) {
        return Promise.resolve();
      }
    } catch (_error) {
      // A transient inconsistent event can be followed by the authoritative update.
    }

    if (deadlineMs <= 0) {
      return Promise.reject(new SonosBackendError(
        'operation_timeout',
        'Sonos topology did not converge before the operation deadline',
        504,
        true
      ));
    }

    return new Promise((resolve, reject) => {
      let settled = false;
      let unsubscribe = (): void => undefined;
      let unsubscribeObsolete = (): void => undefined;
      let timeout: ReturnType<typeof setTimeout> | null = null;
      const finish = (error?: Error): void => {
        if (settled) {
          return;
        }
        settled = true;
        if (timeout !== null) {
          this.clearTimer(timeout);
          timeout = null;
        }
        unsubscribe();
        unsubscribeObsolete();
        if (error) {
          reject(error);
        } else {
          resolve();
        }
      };
      unsubscribe = this.stateStore.subscribe(snapshot => {
        if (isObsolete()) {
          finish();
          return;
        }
        try {
          if (predicate(snapshot)) {
            finish();
          }
        } catch (_error) {
          // Wait for a coherent authoritative topology until the deadline.
        }
      });
      unsubscribeObsolete = onObsolete(() => finish());
      if (settled) {
        return;
      }
      timeout = this.setTimer(() => {
        finish(new SonosBackendError(
          'operation_timeout',
          'Sonos topology did not converge before the operation deadline',
          504,
          true
        ));
      }, Math.min(this.topologyDeadlineMs, deadlineMs));
    });
  }

  private validateRooms(rooms: readonly string[]): asserts rooms is readonly SonosRoomName[] {
    const invalid = rooms.find(roomName => !isSonosRoomName(roomName));
    if (invalid) {
      throw new SonosBackendError('unknown_room', `Unknown Sonos room ${invalid}`, 404);
    }
  }
}

export const isHomeAssistantStateStore = (
  value: unknown
): value is HomeAssistantStateStore => value instanceof HomeAssistantStateStore;
