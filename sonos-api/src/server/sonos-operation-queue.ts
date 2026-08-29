import {
  SonosOperation,
  SonosOperationKind,
  SonosOperationStatus,
} from './sonos-contract';
import {isSonosRoomName, SonosRoomName} from './sonos-room-map';

export interface SonosOperationRunResult {
  status?: 'completed' | 'partial';
  unavailableRooms?: SonosRoomName[];
}

export interface EnqueueSonosOperation {
  kind: SonosOperationKind;
  key: string;
  targetRoom?: SonosRoomName;
  requestedRooms: SonosRoomName[];
  unavailableRooms?: SonosRoomName[];
  run(context: {
    isSuperseded(): boolean;
    isCancelled(): boolean;
    isObsolete(): boolean;
    deadlineAt: number;
    remainingMs(): number;
    recordServiceCall(): void;
    onObsolete(listener: () => void): () => void;
  }): Promise<SonosOperationRunResult | void>;
}

export interface SonosOperationLogRecord {
  event: 'sonos_operation_terminal';
  operationId: string;
  kind: SonosOperation['kind'];
  backend: 'home_assistant';
  status: SonosOperation['status'];
  serviceCallCount: number;
  startedAt: number | null;
  finishedAt: number;
  durationMs: number;
  unavailableRooms: SonosRoomName[];
  failedStep?: string;
}

export interface EnqueuedSonosOperation {
  operation: SonosOperation;
  finished: Promise<SonosOperation>;
  coalesced: boolean;
}

export interface SonosOperationQueueOptions {
  now?: () => number;
  id?: () => string;
  maxRecords?: number;
  terminalRetentionMs?: number;
  operationDeadlineMs?: number;
  setTimeout?: typeof setTimeout;
  clearTimeout?: typeof clearTimeout;
  logger?: (record: SonosOperationLogRecord) => void;
}

interface QueueEntry {
  operation: SonosOperation;
  run: EnqueueSonosOperation['run'];
  finished: Promise<SonosOperation>;
  resolve: (operation: SonosOperation) => void;
  resolved: boolean;
  deadlineTimer: ReturnType<typeof setTimeout> | null;
  obsoleteListeners: Set<() => void>;
}

const clone = (operation: SonosOperation): SonosOperation => ({
  ...operation,
  requestedRooms: [...operation.requestedRooms],
  unavailableRooms: [...operation.unavailableRooms],
  ...(operation.observedTopology
    ? {observedTopology: operation.observedTopology.map(group => ({
      coordinator: group.coordinator,
      members: [...group.members],
    }))}
    : {}),
});

const errorMessage = (error: unknown): string => {
  return error instanceof Error && error.message ? error.message : 'Sonos operation failed';
};

export class SonosOperationQueue {
  private readonly now: () => number;
  private readonly id: () => string;
  private readonly maxRecords: number;
  private readonly terminalRetentionMs: number;
  private readonly operationDeadlineMs: number;
  private readonly setTimer: typeof setTimeout;
  private readonly clearTimer: typeof clearTimeout;
  private readonly logger: (record: SonosOperationLogRecord) => void;
  private readonly records = new Map<string, SonosOperation>();
  private active: QueueEntry | null = null;
  private queued: QueueEntry | null = null;
  private counter = 0;

  constructor(options: SonosOperationQueueOptions = {}) {
    this.now = options.now || Date.now;
    this.id = options.id || (() => `sonos-${this.now()}-${++this.counter}`);
    this.maxRecords = options.maxRecords ?? 100;
    this.terminalRetentionMs = options.terminalRetentionMs ?? 5 * 60 * 1000;
    this.operationDeadlineMs = options.operationDeadlineMs ?? 45 * 1000;
    this.setTimer = options.setTimeout || setTimeout;
    this.clearTimer = options.clearTimeout || clearTimeout;
    this.logger = options.logger || (record => console.log(JSON.stringify(record)));
  }

  enqueue(request: EnqueueSonosOperation): EnqueuedSonosOperation {
    this.pruneExpired();
    const duplicate = [this.active, this.queued].find(entry =>
      entry && entry.operation.key === request.key &&
      (entry.operation.status === 'queued' || entry.operation.status === 'running')
    );
    if (duplicate) {
      return {
        operation: clone(duplicate.operation),
        finished: duplicate.finished.then(clone),
        coalesced: true,
      };
    }

    if (this.active && this.active.operation.status === 'running') {
      this.finishStatus(this.active, 'superseded');
    }
    if (this.queued) {
      this.finishStatus(this.queued, 'superseded');
      this.resolveEntry(this.queued);
      this.queued = null;
    }

    let resolve!: (operation: SonosOperation) => void;
    const finished = new Promise<SonosOperation>(done => {
      resolve = done;
    });
    const createdAt = this.now();
    const operation: SonosOperation = {
      id: this.id(),
      kind: request.kind,
      key: request.key,
      status: 'queued',
      ...(request.targetRoom ? {targetRoom: request.targetRoom} : {}),
      requestedRooms: [...request.requestedRooms],
      unavailableRooms: [...(request.unavailableRooms || [])],
      serviceCallCount: 0,
      createdAt,
      deadlineAt: createdAt + this.operationDeadlineMs,
    };
    const entry: QueueEntry = {
      operation,
      run: request.run,
      finished,
      resolve,
      resolved: false,
      deadlineTimer: null,
      obsoleteListeners: new Set(),
    };
    this.remember(operation);

    if (this.active) {
      this.queued = entry;
    } else {
      this.active = entry;
      void this.runActive();
    }
    return {operation: clone(operation), finished: finished.then(clone), coalesced: false};
  }

  get activeOperation(): SonosOperation | null {
    return this.active ? clone(this.active.operation) : null;
  }

  get queuedOperation(): SonosOperation | null {
    return this.queued ? clone(this.queued.operation) : null;
  }

  getOperation(id: string): SonosOperation | undefined {
    this.pruneExpired();
    const operation = this.records.get(id);
    return operation ? clone(operation) : undefined;
  }

  listOperations(): SonosOperation[] {
    this.pruneExpired();
    return [...this.records.values()].map(clone);
  }

  cancelOperation(id: string, reason = 'Sonos operation cancelled'): SonosOperation | null {
    if (this.queued?.operation.id === id) {
      const entry = this.queued;
      entry.operation.error = reason;
      this.finishStatus(entry, 'cancelled');
      this.resolveEntry(entry);
      this.queued = null;
      return clone(entry.operation);
    }
    if (this.active?.operation.id === id &&
      (this.active.operation.status === 'running' || this.active.operation.status === 'queued')) {
      this.active.operation.error = reason;
      this.finishStatus(this.active, 'cancelled');
      return clone(this.active.operation);
    }
    return null;
  }

  cancelAll(reason = 'Sonos operations cancelled'): SonosOperation[] {
    const cancelled: SonosOperation[] = [];
    if (this.queued) {
      const operation = this.cancelOperation(this.queued.operation.id, reason);
      if (operation) {
        cancelled.push(operation);
      }
    }
    if (this.active) {
      const operation = this.cancelOperation(this.active.operation.id, reason);
      if (operation) {
        cancelled.push(operation);
      }
    }
    return cancelled;
  }

  private async runActive(): Promise<void> {
    const entry = this.active;
    if (!entry) {
      return;
    }
    entry.operation.status = 'running';
    entry.operation.startedAt = this.now();

    if (entry.operation.startedAt >= entry.operation.deadlineAt) {
      entry.operation.error = 'Sonos operation expired before it could start';
      this.finishStatus(entry, 'timed_out');
      this.resolveEntry(entry);
      if (this.active === entry) {
        this.active = this.queued;
        this.queued = null;
      }
      if (this.active) {
        void this.runActive();
      }
      return;
    }

    entry.deadlineTimer = this.setTimer(() => {
      if (entry.operation.status === 'running') {
        entry.operation.error = 'Sonos operation exceeded its acceptance deadline';
        this.finishStatus(entry, 'timed_out');
        this.resolveEntry(entry);
      }
    }, Math.max(0, entry.operation.deadlineAt - entry.operation.startedAt));

    try {
      const result = await entry.run({
        isSuperseded: () => entry.operation.status === 'superseded',
        isCancelled: () => entry.operation.status === 'cancelled',
        isObsolete: () => this.isObsolete(entry),
        deadlineAt: entry.operation.deadlineAt,
        remainingMs: () => Math.max(0, entry.operation.deadlineAt - this.now()),
        recordServiceCall: () => { entry.operation.serviceCallCount += 1; },
        onObsolete: listener => {
          if (this.isObsolete(entry)) {
            listener();
            return () => undefined;
          }
          entry.obsoleteListeners.add(listener);
          return () => entry.obsoleteListeners.delete(listener);
        },
      });
      if (!this.isObsolete(entry)) {
        entry.operation.unavailableRooms = [
          ...(result?.unavailableRooms || entry.operation.unavailableRooms),
        ];
        this.finishStatus(entry, result?.status || 'completed');
      }
    } catch (error) {
      if (!this.isObsolete(entry)) {
        entry.operation.error = errorMessage(error);
        if (error && typeof error === 'object') {
          if ('failedStep' in error && typeof error.failedStep === 'string') {
            entry.operation.failedStep = error.failedStep;
          }
          const observedTopology = 'observedTopology' in error
            ? error.observedTopology
            : undefined;
          if (Array.isArray(observedTopology) && observedTopology.every(group =>
            group && typeof group === 'object' &&
            'coordinator' in group && isSonosRoomName(group.coordinator) &&
            'members' in group && Array.isArray(group.members) &&
            group.members.every(isSonosRoomName)
          )) {
            entry.operation.observedTopology = observedTopology.map(group => ({
              coordinator: group.coordinator,
              members: [...group.members],
            }));
          }
        }
        const code = error && typeof error === 'object' && 'code' in error
          ? String((error as {code: unknown}).code)
          : '';
        this.finishStatus(entry, code === 'operation_timeout' ? 'timed_out' : 'failed');
      }
    } finally {
      if (entry.deadlineTimer) {
        this.clearTimer(entry.deadlineTimer);
        entry.deadlineTimer = null;
      }
      this.resolveEntry(entry);
      if (this.active === entry) {
        this.active = this.queued;
        this.queued = null;
      }
      if (this.active) {
        void this.runActive();
      }
    }
  }

  private finishStatus(entry: QueueEntry, status: SonosOperationStatus): void {
    entry.operation.status = status;
    entry.operation.finishedAt = this.now();
    if (this.isObsolete(entry)) {
      const listeners = [...entry.obsoleteListeners];
      entry.obsoleteListeners.clear();
      for (const listener of listeners) {
        listener();
      }
    }
    this.remember(entry.operation);
    this.logger({
      event: 'sonos_operation_terminal',
      operationId: entry.operation.id,
      kind: entry.operation.kind,
      backend: 'home_assistant',
      status,
      serviceCallCount: entry.operation.serviceCallCount,
      startedAt: entry.operation.startedAt ?? null,
      finishedAt: entry.operation.finishedAt,
      durationMs: entry.operation.startedAt === undefined
        ? 0
        : Math.max(0, entry.operation.finishedAt - entry.operation.startedAt),
      unavailableRooms: [...entry.operation.unavailableRooms],
      ...(entry.operation.failedStep ? {failedStep: entry.operation.failedStep} : {}),
    });
  }

  private isObsolete(entry: QueueEntry): boolean {
    return entry.operation.status === 'superseded' ||
      entry.operation.status === 'cancelled' ||
      entry.operation.status === 'timed_out';
  }

  private resolveEntry(entry: QueueEntry): void {
    if (entry.resolved) {
      return;
    }
    entry.resolved = true;
    entry.resolve(clone(entry.operation));
  }

  private remember(operation: SonosOperation): void {
    this.records.set(operation.id, operation);
    while (this.records.size > this.maxRecords) {
      const oldest = this.records.keys().next().value as string | undefined;
      if (!oldest) {
        break;
      }
      this.records.delete(oldest);
    }
  }

  private pruneExpired(): void {
    const now = this.now();
    for (const [id, operation] of this.records) {
      if (
        operation.finishedAt !== undefined &&
        now - operation.finishedAt >= this.terminalRetentionMs
      ) {
        this.records.delete(id);
      }
    }
  }
}
