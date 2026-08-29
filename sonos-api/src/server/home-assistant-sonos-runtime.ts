import type {Request, Response} from 'express';
import {Router} from 'express';

import type {HomeAssistantClientLike} from './home-assistant-client';
import {HomeAssistantSonosActions} from './home-assistant-sonos-actions';
import {
  executeHomeAssistantSonosPreset,
  HOME_ASSISTANT_SONOS_PRESETS,
  type HomeAssistantSonosPresetPlan,
  isHomeAssistantSonosPresetName,
  planHomeAssistantSonosPreset,
} from './home-assistant-sonos-presets';
import {
  projectCanonicalSonosTopology,
  projectRoomState,
  sonosFreshnessHeaders,
} from './home-assistant-sonos-state';
import type {HomeAssistantStateStore} from './home-assistant-state-store';
import {fetchSonosArtwork, resolveSonosArtworkOwner} from './sonos-artwork';
import type {SonosOperation, SonosStateSnapshot} from './sonos-contract';
import {SonosBackendError} from './sonos-contract';
import {
  isSonosRoomName,
  SONOS_ENTITY_IDS,
  SONOS_ROOM_NAMES,
  SONOS_ROOM_TO_ENTITY,
  type SonosRoomName,
} from './sonos-room-map';

export const CONFIGURED_SONOS_FAVORITES = Object.freeze([
  'Rockboat',
  "735 - Steve Aoki's Remix Radio",
  'Office DJ',
  'Carbon Leaf',
  'Zero 7',
  '53 - SiriusXM Chill',
] as const);

export interface HomeAssistantSonosRuntimeOptions {
  client: HomeAssistantClientLike;
  stateStore: HomeAssistantSonosStateStore;
  actions?: HomeAssistantSonosActions;
  now?: () => number;
  setTimeout?: typeof setTimeout;
  clearTimeout?: typeof clearTimeout;
}

export interface HomeAssistantSonosStateStore extends Pick<
  HomeAssistantStateStore,
  'start' | 'stop' | 'snapshot' | 'assertCommandable' | 'subscribe'
> {}

export interface HomeAssistantSonosHealth {
  ready: boolean;
  freshness: SonosStateSnapshot['freshness'];
  missingRooms: SonosRoomName[];
  unavailableRooms: SonosRoomName[];
  missingFavorites: string[];
  missingPresetSources: string[];
  error?: string;
}

const jsonError = (error: unknown): {statusCode: number; body: Record<string, unknown>} => {
  if (error instanceof SonosBackendError) {
    return {
      statusCode: error.statusCode,
      body: {error: error.message, code: error.code, retryable: error.retryable},
    };
  }
  const message = error instanceof Error && error.message
    ? error.message
    : 'Sonos request failed';
  return {statusCode: 502, body: {error: message, code: 'backend_error'}};
};

const roomParam = (value: string | string[] | undefined): SonosRoomName => {
  const candidate = Array.isArray(value) ? value[0] : value;
  if (!isSonosRoomName(candidate)) {
    throw new SonosBackendError(
      'unknown_room',
      `Unknown Sonos room ${candidate || '(empty)'}`,
      404
    );
  }
  return candidate;
};

const stringParam = (value: string | string[] | undefined, label: string): string => {
  const candidate = Array.isArray(value) ? value[0] : value;
  if (!candidate) {
    throw new SonosBackendError('invalid_request', `${label} is required`, 400);
  }
  return candidate;
};

const setFreshnessHeaders = (res: Response, snapshot: SonosStateSnapshot): void => {
  for (const [name, value] of Object.entries(sonosFreshnessHeaders(snapshot))) {
    res.setHeader(name, value);
  }
};

const observedMembers = (
  snapshot: SonosStateSnapshot,
  operation: SonosOperation
): {joinedRooms: SonosRoomName[]; missingRooms: SonosRoomName[]} => {
  if (!operation.targetRoom || snapshot.freshness === 'unknown') {
    return {joinedRooms: [], missingRooms: [...operation.requestedRooms]};
  }
  const targetState = snapshot.entities.get(SONOS_ROOM_TO_ENTITY[operation.targetRoom]);
  const rawMembers = targetState?.attributes.group_members;
  const memberIds = Array.isArray(rawMembers)
    ? new Set(rawMembers.filter((value): value is string => typeof value === 'string'))
    : new Set<string>();
  const joinedRooms = operation.requestedRooms.filter(room =>
    memberIds.has(SONOS_ROOM_TO_ENTITY[room])
  );
  return {
    joinedRooms,
    missingRooms: operation.requestedRooms.filter(room => !joinedRooms.includes(room)),
  };
};

const operationMessage = (operation: SonosOperation, missingRooms: SonosRoomName[]): string => {
  const target = operation.targetRoom ? ` to ${operation.targetRoom}` : '';
  if (operation.status === 'running' || operation.status === 'queued') {
    return `Applying Sonos ${operation.kind}${target}`;
  }
  if (operation.status === 'completed') {
    return `Sonos ${operation.kind}${target} completed`;
  }
  if (operation.status === 'partial') {
    return `Sonos ${operation.kind}${target} completed with unavailable rooms: ${missingRooms.join(', ')}`;
  }
  return operation.error || `Sonos ${operation.kind}${target} ${operation.status}`;
};

const compatibilityOperation = (
  operation: SonosOperation,
  snapshot: SonosStateSnapshot
): Record<string, unknown> => {
  const observed = observedMembers(snapshot, operation);
  return {
    ...operation,
    kind: operation.kind === 'join_all' ? 'group_all_to_room' : operation.kind,
    targetRoom: operation.targetRoom,
    roomNames: [...operation.requestedRooms],
    joinedRooms: observed.joinedRooms,
    missingRooms: [...new Set([...observed.missingRooms, ...operation.unavailableRooms])],
    createdAt: new Date(operation.createdAt).toISOString(),
    expiresAt: new Date(operation.deadlineAt).toISOString(),
    ...(operation.finishedAt === undefined
      ? {}
      : {finishedAt: new Date(operation.finishedAt).toISOString()}),
    message: operationMessage(operation, observed.missingRooms),
  };
};

export class HomeAssistantSonosRuntime {
  readonly actions: HomeAssistantSonosActions;

  private readonly client: HomeAssistantClientLike;
  private readonly stateStore: HomeAssistantSonosStateStore;
  private readonly now: () => number;
  private readonly setTimer: typeof setTimeout;
  private readonly clearTimer: typeof clearTimeout;

  constructor(options: HomeAssistantSonosRuntimeOptions) {
    this.client = options.client;
    this.stateStore = options.stateStore;
    this.actions = options.actions || new HomeAssistantSonosActions({
      client: options.client,
      stateStore: options.stateStore,
      now: options.now,
    });
    this.now = options.now || Date.now;
    this.setTimer = options.setTimeout || setTimeout;
    this.clearTimer = options.clearTimeout || clearTimeout;
  }

  async start(): Promise<void> {
    await this.stateStore.start();
  }

  stop(): void {
    this.actions.operationQueue.cancelAll('Sonos API is shutting down');
    this.stateStore.stop();
  }

  snapshot(): SonosStateSnapshot {
    return this.stateStore.snapshot();
  }

  health(): HomeAssistantSonosHealth {
    const snapshot = this.snapshot();
    const missingRooms: SonosRoomName[] = [];
    const unavailableRooms: SonosRoomName[] = [];
    const missingFavorites = new Set<string>();
    const missingPresetSources = new Set<string>();

    for (const roomName of SONOS_ROOM_NAMES) {
      const state = snapshot.entities.get(SONOS_ROOM_TO_ENTITY[roomName]);
      if (!state) {
        missingRooms.push(roomName);
        continue;
      }
      if (state.state === 'unknown' || state.state === 'unavailable') {
        unavailableRooms.push(roomName);
      }
      const sources = new Set(
        Array.isArray(state.attributes.source_list)
          ? state.attributes.source_list.filter((source): source is string => typeof source === 'string')
          : []
      );
      for (const favorite of CONFIGURED_SONOS_FAVORITES) {
        if (!sources.has(favorite)) {
          missingFavorites.add(`${roomName}:${favorite}`);
        }
      }
    }

    for (const [name, preset] of Object.entries(HOME_ASSISTANT_SONOS_PRESETS)) {
      const coordinator = preset.players[0].roomName;
      const state = snapshot.entities.get(SONOS_ROOM_TO_ENTITY[coordinator]);
      const sources = Array.isArray(state?.attributes.source_list)
        ? state.attributes.source_list
        : [];
      if (!sources.includes(preset.source)) {
        missingPresetSources.add(`${name}:${preset.source}`);
      }
    }

    const ready = snapshot.freshness === 'live' &&
      missingRooms.length === 0 && unavailableRooms.length === 0 &&
      missingFavorites.size === 0 && missingPresetSources.size === 0;
    return {
      ready,
      freshness: snapshot.freshness,
      missingRooms,
      unavailableRooms,
      missingFavorites: [...missingFavorites],
      missingPresetSources: [...missingPresetSources],
      ...(snapshot.lastError ? {error: snapshot.lastError} : {}),
    };
  }

  zones(snapshot: SonosStateSnapshot = this.snapshot()): unknown {
    return this.topology(snapshot).zones;
  }

  topology(snapshot: SonosStateSnapshot = this.snapshot()) {
    return projectCanonicalSonosTopology(snapshot, {
      now: this.now,
      artworkPath: room => this.artworkPath(snapshot, room),
    });
  }

  roomState(
    roomName: SonosRoomName,
    snapshot: SonosStateSnapshot = this.snapshot()
  ): unknown {
    return projectRoomState(snapshot, roomName, {
      now: this.now,
      artworkPath: room => this.artworkPath(snapshot, room),
    });
  }

  async artwork(
    roomName: SonosRoomName,
    snapshot: SonosStateSnapshot = this.snapshot()
  ): Promise<Awaited<ReturnType<typeof fetchSonosArtwork>>> {
    return fetchSonosArtwork(this.client, snapshot, roomName);
  }

  async favorite(roomName: SonosRoomName, favoriteName: string): Promise<void> {
    if (!(CONFIGURED_SONOS_FAVORITES as readonly string[]).includes(favoriteName)) {
      throw new SonosBackendError('unknown_favorite', `Unknown Sonos favorite ${favoriteName}`, 404);
    }
    await this.actions.favorite(roomName, favoriteName);
  }

  applyPreset(name: string): SonosOperation {
    if (!isHomeAssistantSonosPresetName(name)) {
      throw new SonosBackendError('unknown_preset', `Unknown Sonos preset ${name}`, 404);
    }
    const plan = planHomeAssistantSonosPreset(name);
    const entityIds = [...new Set([
      ...plan.members,
      ...plan.pauseOthers,
    ])].map(room => SONOS_ROOM_TO_ENTITY[room]);
    this.stateStore.assertCommandable(entityIds);
    const coordinatorState = this.snapshot().entities.get(
      SONOS_ROOM_TO_ENTITY[plan.coordinator]
    );
    const sourceList = coordinatorState?.attributes.source_list;
    if (!Array.isArray(sourceList) || !sourceList.includes(plan.source)) {
      throw new SonosBackendError(
        'preset_source_unavailable',
        `${plan.source} is unavailable for ${plan.coordinator}`,
        503,
        true
      );
    }

    return this.actions.operationQueue.enqueue({
      kind: 'preset',
      key: `preset:${name}`,
      targetRoom: plan.coordinator,
      requestedRooms: [...plan.members],
      run: async context => {
        const result = await executeHomeAssistantSonosPreset(name, {
          client: {
            callService: async (domain, service, data) => {
              context.recordServiceCall();
              return this.client.callService(domain, service, data);
            },
          },
          observe: () => projectCanonicalSonosTopology(this.snapshot()).zones,
          isObsolete: context.isObsolete,
        });
        if (result.status === 'cancelled' || context.isObsolete()) {
          return;
        }
        if (result.status === 'failed') {
          const failure = new SonosBackendError(
            'preset_step_failed',
            `Preset ${name} failed at ${result.failedStep.id}`,
            502,
            false
          );
          Object.assign(failure, {
            failedStep: result.failedStep.id,
            observedTopology: (result.observation || []).map(zone => ({
              coordinator: zone.coordinator.roomName,
              members: zone.members.map(member => member.roomName),
            })),
          });
          throw failure;
        }
        await this.waitForPresetConvergence(
          plan,
          context.isObsolete,
          context.remainingMs
        );
      },
    }).operation;
  }

  status(): Record<string, unknown> {
    const snapshot = this.snapshot();
    const queued = this.actions.operationQueue.queuedOperation;
    const running = this.actions.operationQueue.activeOperation;
    // A queued operation is necessarily newer than the operation it superseded,
    // even when both were created during the same clock tick.
    const active = queued?.status === 'queued'
      ? queued
      : running && ['queued', 'running'].includes(running.status)
        ? running
        : undefined;
    const latestTerminal = this.actions.operationQueue.listOperations()
      .filter(operation => !['queued', 'running'].includes(operation.status))
      .sort((left, right) => (right.finishedAt || 0) - (left.finishedAt || 0))[0];
    return {
      activeIntent: active && ['queued', 'running'].includes(active.status)
        ? compatibilityOperation(active, snapshot)
        : null,
      recentIntent: latestTerminal
        ? compatibilityOperation(latestTerminal, snapshot)
        : null,
      serverTime: new Date(this.now()).toISOString(),
    };
  }

  private waitForPresetConvergence(
    plan: HomeAssistantSonosPresetPlan,
    isObsolete: () => boolean,
    remainingMs: () => number
  ): Promise<void> {
    const expectedEntityIds = plan.members.map(roomName => SONOS_ROOM_TO_ENTITY[roomName]);
    const expectedSet = new Set<string>(expectedEntityIds);
    const coordinatorEntityId = SONOS_ROOM_TO_ENTITY[plan.coordinator];
    const expectedVolumes = new Map(
      HOME_ASSISTANT_SONOS_PRESETS[plan.name].players.map(player => [
        SONOS_ROOM_TO_ENTITY[player.roomName],
        player.volume,
      ])
    );
    const matches = (snapshot: SonosStateSnapshot): boolean => {
      if (snapshot.freshness !== 'live') {
        return false;
      }
      for (const entityId of expectedEntityIds) {
        const state = snapshot.entities.get(entityId);
        if (!state || state.state === 'unknown' || state.state === 'unavailable') {
          return false;
        }
        const members = state.attributes.group_members;
        if (
          !Array.isArray(members) ||
          members.length !== expectedEntityIds.length ||
          members[0] !== coordinatorEntityId ||
          members.some(member => typeof member !== 'string' || !expectedSet.has(member))
        ) {
          return false;
        }
        const volume = Number(state.attributes.volume_level);
        if (
          !Number.isFinite(volume) ||
          Math.round(volume * 100) !== expectedVolumes.get(entityId)
        ) {
          return false;
        }
      }
      const source = snapshot.entities.get(coordinatorEntityId)?.attributes.source;
      if (source !== plan.source) {
        return false;
      }
      return plan.pauseOthers.every(roomName => {
        const state = snapshot.entities.get(SONOS_ROOM_TO_ENTITY[roomName]);
        return state?.state === 'paused';
      });
    };

    if (isObsolete() || matches(this.snapshot())) {
      return Promise.resolve();
    }
    if (remainingMs() <= 0) {
      return Promise.reject(this.presetConvergenceTimeout(plan));
    }

    return new Promise((resolve, reject) => {
      let settled = false;
      let pollTimer: ReturnType<typeof setTimeout> | null = null;
      let unsubscribe = (): void => undefined;
      const finish = (error?: Error): void => {
        if (settled) {
          return;
        }
        settled = true;
        if (pollTimer) {
          this.clearTimer(pollTimer);
        }
        unsubscribe();
        if (error) {
          reject(error);
        } else {
          resolve();
        }
      };
      const check = (snapshot: SonosStateSnapshot): void => {
        if (isObsolete()) {
          finish();
        } else if (matches(snapshot)) {
          finish();
        }
      };
      const schedulePoll = (): void => {
        if (settled) {
          return;
        }
        const remaining = remainingMs();
        if (remaining <= 0) {
          finish(this.presetConvergenceTimeout(plan));
          return;
        }
        pollTimer = this.setTimer(() => {
          check(this.snapshot());
          schedulePoll();
        }, Math.min(25, remaining));
      };

      unsubscribe = this.stateStore.subscribe(check);
      check(this.snapshot());
      schedulePoll();
    });
  }

  private presetConvergenceTimeout(plan: HomeAssistantSonosPresetPlan): SonosBackendError {
    return new SonosBackendError(
      'operation_timeout',
      `Preset ${plan.name} did not converge before the operation deadline`,
      504,
      true
    );
  }

  private artworkPath(
    snapshot: SonosStateSnapshot,
    roomName: SonosRoomName
  ): string {
    const ownerRoom = resolveSonosArtworkOwner(snapshot, roomName);
    const state = snapshot.entities.get(SONOS_ROOM_TO_ENTITY[ownerRoom]);
    const picture = typeof state?.attributes.entity_picture === 'string'
      ? state.attributes.entity_picture
      : '';
    let picturePath = '';
    try {
      const parsed = new URL(picture, 'http://homeassistant.invalid');
      picturePath = parsed.origin === 'http://homeassistant.invalid'
        ? parsed.pathname
        : '';
    } catch (_error) {
      picturePath = '';
    }
    const revision = JSON.stringify([
      picturePath,
      state?.attributes.media_content_id || '',
      state?.attributes.media_title || '',
      state?.attributes.media_artist || '',
      state?.attributes.media_album_name || '',
      state?.attributes.media_channel || '',
    ]);
    let hash = 2166136261;
    for (let index = 0; index < revision.length; index += 1) {
      hash ^= revision.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return `./sonos/${encodeURIComponent(roomName)}/artwork?rev=${(hash >>> 0).toString(36)}`;
  }
}

export const createHomeAssistantSonosRouter = (
  runtime: HomeAssistantSonosRuntime
): Router => {
  const app = Router();
  const wrap = (
    handler: (req: Request, res: Response) => Promise<void> | void
  ) => async (req: Request, res: Response): Promise<void> => {
    try {
      await handler(req, res);
    } catch (error) {
      const failure = jsonError(error);
      if (!res.headersSent) {
        res.status(failure.statusCode).json(failure.body);
      }
    }
  };

  app.get('/sonos/zones', wrap((_req, res) => {
    const snapshot = runtime.snapshot();
    const topology = runtime.topology(snapshot);
    setFreshnessHeaders(res, snapshot);
    if (topology.unknownRooms.length > 0) {
      res.setHeader('X-Sonos-Unavailable-Rooms', topology.unknownRooms.join(','));
    }
    res.status(200).json(topology.zones);
  }));

  app.get('/sonos/:room/state', wrap((req, res) => {
    const room = roomParam(req.params.room);
    const snapshot = runtime.snapshot();
    setFreshnessHeaders(res, snapshot);
    res.status(200).json(runtime.roomState(room, snapshot));
  }));

  app.get('/sonos/:room/artwork', wrap(async (req, res) => {
    const room = roomParam(req.params.room);
    const snapshot = runtime.snapshot();
    const artwork = await runtime.artwork(room, snapshot);
    setFreshnessHeaders(res, snapshot);
    res.setHeader('Content-Type', artwork.contentType);
    res.setHeader('Cache-Control', artwork.cacheControl);
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.status(200).send(Buffer.from(artwork.body));
  }));

  app.get('/sonos/:room/play', wrap(async (req, res) => {
    await runtime.actions.play(roomParam(req.params.room));
    res.status(200).json({status: 'success'});
  }));
  app.get('/sonos/:room/pause', wrap(async (req, res) => {
    await runtime.actions.pause(roomParam(req.params.room));
    res.status(200).json({status: 'success'});
  }));
  app.get('/sonos/:room/playpause', wrap(async (req, res) => {
    await runtime.actions.playPause(roomParam(req.params.room));
    res.status(200).json({status: 'success'});
  }));
  app.get('/sonos/:room/next', wrap(async (req, res) => {
    await runtime.actions.next(roomParam(req.params.room));
    res.status(200).json({status: 'success'});
  }));
  app.get('/sonos/:room/favorite/:name', wrap(async (req, res) => {
    const room = roomParam(req.params.room);
    const favorite = stringParam(req.params.name, 'Favorite');
    await runtime.favorite(room, favorite);
    res.status(200).json({status: 'success'});
  }));
  app.get('/sonos/:room/join/:target', wrap((req, res) => {
    const operation = runtime.actions.join(
      roomParam(req.params.room),
      roomParam(req.params.target)
    ).operation;
    res.status(202).json({operation});
  }));
  app.get('/sonos/:room/leave', wrap((req, res) => {
    const operation = runtime.actions.leave(roomParam(req.params.room)).operation;
    res.status(202).json({operation});
  }));
  app.get('/sonos/:room/groupVolume/:value', wrap(async (req, res) => {
    const value = stringParam(req.params.value, 'Volume');
    if (!/^[+-]?\d+$/.test(value)) {
      throw new SonosBackendError('invalid_volume', `Invalid volume ${value}`, 400);
    }
    await runtime.actions.groupVolume(
      roomParam(req.params.room),
      value
    );
    res.status(200).json({status: 'success'});
  }));
  app.get('/sonos/:room/volume/:value', wrap(async (req, res) => {
    const rawValue = stringParam(req.params.value, 'Volume');
    const value = Number(rawValue);
    if (!Number.isFinite(value) || !/^\d+(?:\.\d+)?$/.test(rawValue)) {
      throw new SonosBackendError('invalid_volume', `Invalid volume ${rawValue}`, 400);
    }
    await runtime.actions.setRoomVolume(roomParam(req.params.room), value);
    res.status(200).json({status: 'success'});
  }));
  app.get('/sonos/:room/preset/:name', wrap((req, res) => {
    const requestedRoom = roomParam(req.params.room);
    const name = stringParam(req.params.name, 'Preset').replace('$room', requestedRoom);
    const operation = runtime.applyPreset(name);
    res.status(202).json({operation});
  }));
  app.get('/same/:room', wrap(async (req, res) => {
    await runtime.actions.normalizeGroupVolume(roomParam(req.params.room));
    res.status(200).json({status: 'success'});
  }));
  const groupAllHandler = wrap((req, res) => {
    const body = req.body as Record<string, unknown> | undefined;
    if (!body || typeof body !== 'object' || Array.isArray(body)) {
      throw new SonosBackendError('invalid_request', 'A JSON request body is required', 400);
    }
    const targetRoom = roomParam(typeof body.targetRoom === 'string' ? body.targetRoom : undefined);
    if (!Array.isArray(body.roomNames) || body.roomNames.some(room => !isSonosRoomName(room))) {
      throw new SonosBackendError('invalid_request', 'roomNames must contain configured rooms', 400);
    }
    const roomNames = body.roomNames as SonosRoomName[];
    if (roomNames.length === 0) {
      throw new SonosBackendError('invalid_request', 'roomNames must not be empty', 400);
    }
    if (new Set(roomNames).size !== roomNames.length) {
      throw new SonosBackendError('invalid_request', 'roomNames must not contain duplicates', 400);
    }
    if (!roomNames.includes(targetRoom)) {
      throw new SonosBackendError('invalid_request', 'targetRoom must be included in roomNames', 400);
    }
    const operation = runtime.actions.joinAll(
      targetRoom,
      roomNames
    ).operation;
    res.status(202).json({intent: compatibilityOperation(operation, runtime.snapshot())});
  });
  const statusHandler = wrap((_req, res) => {
    res.status(200).json(runtime.status());
  });
  app.post('/sonos-intents/group-all', groupAllHandler);
  app.post('/intents/sonos/group-all', groupAllHandler);
  app.get('/sonos-intents/status', statusHandler);
  app.get('/intents/sonos/status', statusHandler);

  app.get('/up', wrap(async (_req, res) => {
    const state = runtime.roomState('Bedroom') as {playbackState: string};
    if (state.playbackState === 'PAUSED_PLAYBACK') {
      await runtime.actions.play('Bedroom');
    } else {
      await runtime.actions.groupVolume('Bedroom', '+1');
    }
    res.status(200).json({status: 'success'});
  }));
  app.get('/down', wrap(async (_req, res) => {
    const state = runtime.roomState('Bedroom') as {playbackState: string; volume: number};
    if (state.playbackState === 'PLAYING' && state.volume <= 3) {
      await runtime.actions.pause('Bedroom');
    } else {
      await runtime.actions.groupVolume('Bedroom', '-1');
    }
    res.status(200).json({status: 'success'});
  }));

  for (const deprecatedPath of ['/pause', '/play', '/tv', '/07', '/quiet']) {
    app.get(deprecatedPath, (_req, res) => {
      res.status(410).json({
        error: `Deprecated Sonos route ${deprecatedPath} has no live repository caller`,
        code: 'deprecated_route',
      });
    });
  }

  app.all(/^\/sonos(?:\/|$)/, (_req, res) => {
    res.status(404).json({error: 'Unsupported Sonos route', code: 'unsupported_route'});
  });
  return app;
};

export const expectedSonosEntityIds = (): readonly string[] => SONOS_ENTITY_IDS;
