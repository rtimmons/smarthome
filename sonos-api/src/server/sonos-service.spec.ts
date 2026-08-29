import assert from 'node:assert/strict';
import type {AddressInfo} from 'node:net';
import test from 'node:test';
import {Router} from 'express';

import type {SonosBackendMode} from './config';
import type {HomeAssistantClientLike} from './home-assistant-client';
import {
  CONFIGURED_SONOS_FAVORITES,
  HomeAssistantSonosRuntime,
  type HomeAssistantSonosStateStore,
} from './home-assistant-sonos-runtime';
import {haSnapshot, haState} from './home-assistant-test-fixtures';
import {createApp} from './index';
import type {SonosNodeReadinessMonitor} from './sonos-node-readiness';
import {
  createShadowObserver,
  createSonosService,
  type SonosServiceConfig,
} from './sonos-service';
import type {ShadowZoneLike} from './sonos-shadow-compare';
import type {SonosStateSnapshot} from './sonos-contract';
import {SONOS_ROOM_NAMES} from './sonos-room-map';

const config = (backendMode: SonosBackendMode, token = ''): SonosServiceConfig => ({
  backendMode,
  sonosUrl: 'http://node.invalid:5005',
  homeAssistantRestUrl: 'http://supervisor/core/api',
  homeAssistantWebSocketUrl: 'ws://supervisor/core/websocket',
  homeAssistantToken: token,
});

const nodeMonitor = (
  ready = true,
  error?: string
): SonosNodeReadinessMonitor => ({
  start: async () => undefined,
  stop: async () => undefined,
  check: async () => undefined,
  snapshot: () => ({
    ready,
    checkedAt: 1_000,
    ...(ready ? {statusCode: 200} : {error: error || 'node unavailable'}),
  }),
});

const RETAINED_MUTATING_ROUTES = [
  {method: 'GET', path: '/sonos/Kitchen/play'},
  {method: 'GET', path: '/sonos/Kitchen/pause'},
  {method: 'GET', path: '/sonos/Kitchen/playpause'},
  {method: 'GET', path: '/sonos/Kitchen/next'},
  {method: 'GET', path: '/sonos/Kitchen/favorite/Rockboat'},
  {method: 'GET', path: '/sonos/Kitchen/join/Office'},
  {method: 'GET', path: '/sonos/Kitchen/leave'},
  {method: 'GET', path: '/sonos/Kitchen/groupVolume/%2D5'},
  {method: 'GET', path: '/sonos/Kitchen/volume/12'},
  {method: 'GET', path: '/sonos/Kitchen/preset/default'},
  {method: 'GET', path: '/same/Kitchen'},
  {method: 'GET', path: '/up'},
  {method: 'GET', path: '/down'},
  {method: 'GET', path: '/pause'},
  {method: 'GET', path: '/play'},
  {method: 'GET', path: '/tv'},
  {method: 'GET', path: '/07'},
  {method: 'GET', path: '/quiet'},
  {method: 'POST', path: '/intents/sonos/group-all'},
] as const;

const RETAINED_READ_ROUTES = [
  {method: 'GET', path: '/sonos/zones'},
  {method: 'GET', path: '/sonos/Kitchen/state'},
  {method: 'GET', path: '/sonos/Kitchen/artwork'},
  {method: 'GET', path: '/intents/sonos/status'},
] as const;

class MutableHealthStateStore implements HomeAssistantSonosStateStore {
  constructor(public current: SonosStateSnapshot) {}

  async start(): Promise<void> {}
  stop(): void {}
  snapshot(): SonosStateSnapshot {
    return this.current;
  }
  assertCommandable(): void {}
  subscribe(): () => void {
    return () => undefined;
  }
}

const healthSnapshot = (options: {
  freshness?: SonosStateSnapshot['freshness'];
  missingRoom?: (typeof SONOS_ROOM_NAMES)[number];
  unavailableRoom?: (typeof SONOS_ROOM_NAMES)[number];
  lastError?: string;
} = {}): SonosStateSnapshot => haSnapshot(
  SONOS_ROOM_NAMES
    .filter(roomName => roomName !== options.missingRoom)
    .map(roomName => haState(roomName, {
      state: roomName === options.unavailableRoom ? 'unavailable' : 'idle',
      attributes: {
        source_list: [...CONFIGURED_SONOS_FAVORITES, 'TV'],
        entity_picture:
          `/api/media_player_proxy/media_player.${roomName.toLowerCase().replace(/ /g, '_')}` +
          '?token=synthetic-health-picture-token',
      },
    })),
  {
    freshness: options.freshness ?? 'live',
    connected: (options.freshness ?? 'live') === 'live',
    ageMs: options.freshness === 'stale' ? 1_000 : 0,
    ...(options.lastError ? {lastError: options.lastError} : {}),
  }
);

test('node mode is the ready rollback default and does not require a HA token', async () => {
  const service = createSonosService(config('node'), {
    createNodeReadinessMonitor: () => nodeMonitor(),
  });
  await service.start();
  assert.deepEqual(service.health(), {
    statusCode: 200,
    body: {
      status: 'ok',
      ready: true,
      backendMode: 'node',
      node: {ready: true, checkedAt: 1_000, statusCode: 200},
    },
  });
  await service.stop();
});

test('node mode fails readiness when its write backend is unavailable', async () => {
  const service = createSonosService(config('node'), {
    createNodeReadinessMonitor: () => nodeMonitor(false),
  });
  await service.start();
  assert.deepEqual(service.health(), {
    statusCode: 503,
    body: {
      status: 'not_ready',
      ready: false,
      backendMode: 'node',
      node: {ready: false, checkedAt: 1_000, error: 'node unavailable'},
    },
  });
  await service.stop();
});

test('shadow mode remains node-ready while exposing HA diagnostics', async () => {
  const service = createSonosService(config('shadow'), {
    createNodeReadinessMonitor: () => nodeMonitor(),
  });
  await service.start();
  const health = service.health();
  assert.equal(health.statusCode, 200);
  assert.equal(health.body.ready, true);
  assert.equal(health.body.backendMode, 'shadow');
  assert.deepEqual(health.body.node, {
    ready: true,
    checkedAt: 1_000,
    statusCode: 200,
  });
  assert.deepEqual(health.body.homeAssistant, {
    ready: false,
    error: 'SUPERVISOR_TOKEN is required for Home Assistant mode',
  });
  await service.stop();
});

test('shadow mode readiness follows node even when HA diagnostics are available', async () => {
  const runtime = {
    start: async () => undefined,
    stop: () => undefined,
    health: () => ({ready: true}),
    zones: () => [],
  } as unknown as HomeAssistantSonosRuntime;
  const service = createSonosService(config('shadow', 'token'), {
    createNodeReadinessMonitor: () => nodeMonitor(false, 'node write backend unavailable'),
    createHomeAssistantRuntime: () => runtime,
  });
  await service.start();
  const health = service.health();
  assert.equal(health.statusCode, 503);
  assert.equal(health.body.ready, false);
  assert.deepEqual(health.body.node, {
    ready: false,
    checkedAt: 1_000,
    error: 'node write backend unavailable',
  });
  assert.deepEqual(health.body.homeAssistant, {ready: true});
  await service.stop();
});

test('shadow mode keeps node available when the HA observer fails to start', async () => {
  const runtime = {
    start: async () => {
      throw new Error('HA websocket unavailable');
    },
    stop: () => undefined,
    health: () => ({ready: true}),
    zones: () => [],
  } as unknown as HomeAssistantSonosRuntime;
  const service = createSonosService(config('shadow', 'token'), {
    createNodeReadinessMonitor: () => nodeMonitor(),
    createHomeAssistantRuntime: () => runtime,
  });

  await service.start();
  assert.deepEqual(service.health(), {
    statusCode: 200,
    body: {
      status: 'ok',
      ready: true,
      backendMode: 'shadow',
      node: {ready: true, checkedAt: 1_000, statusCode: 200},
      homeAssistant: {ready: false, error: 'HA websocket unavailable'},
    },
  });
  await service.stop();
});

test('shadow mode routes every retained mutating action only to node', async () => {
  let nodeWrites = 0;
  let homeAssistantRouterMounts = 0;
  let homeAssistantReads = 0;
  const nodeRouter = Router();
  nodeRouter.use((req, res) => {
    nodeWrites += 1;
    res.status(200).json({method: req.method, path: req.path});
  });
  const runtime = {
    start: async () => undefined,
    stop: () => undefined,
    health: () => ({ready: true}),
    zones: () => {
      homeAssistantReads += 1;
      return [];
    },
  } as unknown as HomeAssistantSonosRuntime;
  const service = createSonosService(config('shadow', 'token'), {
    nodeRouter,
    createNodeReadinessMonitor: () => nodeMonitor(),
    createHomeAssistantRuntime: () => runtime,
    createHomeAssistantRouter: () => {
      homeAssistantRouterMounts += 1;
      const router = Router();
      router.use((_req, res) => res.status(500).json({error: 'HA write attempted'}));
      return router;
    },
  });
  await service.start();
  const app = createApp(service);
  const server = await new Promise<ReturnType<typeof app.listen>>((resolve, reject) => {
    const listening = app.listen(0, '127.0.0.1', () => resolve(listening));
    listening.once('error', reject);
  });
  const address = server.address() as AddressInfo;

  try {
    for (const action of RETAINED_MUTATING_ROUTES) {
      const response = await fetch(
        `http://127.0.0.1:${address.port}${action.path}`,
        {
          method: action.method,
          ...(action.method === 'POST'
            ? {
              headers: {'content-type': 'application/json'},
              body: JSON.stringify({targetRoom: 'Kitchen'}),
            }
            : {}),
        }
      );
      assert.equal(response.status, 200, action.path);
      assert.deepEqual(await response.json(), {
        method: action.method,
        path: action.path,
      });
    }
    assert.equal(nodeWrites, RETAINED_MUTATING_ROUTES.length,
      'each action reaches the node router exactly once');
    assert.equal(homeAssistantRouterMounts, 0,
      'the Home Assistant command router is never mounted in shadow mode');
    assert.equal(homeAssistantReads, 0,
      'a write does not invoke even the Home Assistant read observer');
  } finally {
    await new Promise<void>((resolve, reject) => {
      server.close(error => error ? reject(error) : resolve());
    });
    await service.stop();
  }
});

test('node and HA modes route the same retained action matrix to exactly one backend', async () => {
  for (const backendMode of ['node', 'home_assistant'] as const) {
    let nodeRequests = 0;
    let homeAssistantRequests = 0;
    const nodeRouter = Router();
    nodeRouter.use((req, res) => {
      nodeRequests += 1;
      res.status(200).json({backend: 'node', method: req.method, path: req.path});
    });
    const homeAssistantRouter = Router();
    homeAssistantRouter.use((req, res) => {
      homeAssistantRequests += 1;
      res.status(200).json({backend: 'home_assistant', method: req.method, path: req.path});
    });
    const runtime = {
      start: async () => undefined,
      stop: () => undefined,
      health: () => ({ready: true}),
    } as unknown as HomeAssistantSonosRuntime;
    const service = createSonosService(config(backendMode, 'token'), {
      nodeRouter,
      createNodeReadinessMonitor: () => nodeMonitor(),
      createHomeAssistantRuntime: () => runtime,
      createHomeAssistantRouter: () => homeAssistantRouter,
    });
    await service.start();
    const app = createApp(service);
    const server = await new Promise<ReturnType<typeof app.listen>>((resolve, reject) => {
      const listening = app.listen(0, '127.0.0.1', () => resolve(listening));
      listening.once('error', reject);
    });
    const address = server.address() as AddressInfo;

    try {
      for (const action of RETAINED_MUTATING_ROUTES) {
        const response = await fetch(
          `http://127.0.0.1:${address.port}${action.path}`,
          {
            method: action.method,
            ...(action.method === 'POST'
              ? {
                headers: {'content-type': 'application/json'},
                body: JSON.stringify({
                  targetRoom: 'Kitchen',
                  roomNames: ['Kitchen'],
                }),
              }
              : {}),
          }
        );
        assert.equal(response.status, 200, `${backendMode} ${action.path}`);
        assert.deepEqual(await response.json(), {
          backend: backendMode === 'node' ? 'node' : 'home_assistant',
          method: action.method,
          path: action.path,
        });
      }
      const expectedCount = RETAINED_MUTATING_ROUTES.length;
      assert.equal(nodeRequests, backendMode === 'node' ? expectedCount : 0,
        `${backendMode} node request count`);
      assert.equal(homeAssistantRequests,
        backendMode === 'home_assistant' ? expectedCount : 0,
        `${backendMode} Home Assistant request count`);
    } finally {
      await new Promise<void>((resolve, reject) => {
        server.close(error => error ? reject(error) : resolve());
      });
      await service.stop();
    }
  }
});

test('node and HA modes route every retained read family to exactly one backend', async () => {
  for (const backendMode of ['node', 'home_assistant'] as const) {
    let nodeRequests = 0;
    let homeAssistantRequests = 0;
    const nodeRouter = Router();
    nodeRouter.use((req, res) => {
      nodeRequests += 1;
      res.status(206).type('application/json').send(JSON.stringify({
        backend: 'node',
        method: req.method,
        path: req.path,
      }));
    });
    const homeAssistantRouter = Router();
    homeAssistantRouter.use((req, res) => {
      homeAssistantRequests += 1;
      res.status(206).type('application/json').send(JSON.stringify({
        backend: 'home_assistant',
        method: req.method,
        path: req.path,
      }));
    });
    const runtime = {
      start: async () => undefined,
      stop: () => undefined,
      health: () => ({ready: true}),
    } as unknown as HomeAssistantSonosRuntime;
    const service = createSonosService(config(backendMode, 'token'), {
      nodeRouter,
      createNodeReadinessMonitor: () => nodeMonitor(),
      createHomeAssistantRuntime: () => runtime,
      createHomeAssistantRouter: () => homeAssistantRouter,
    });
    await service.start();
    const app = createApp(service);
    const server = await new Promise<ReturnType<typeof app.listen>>((resolve, reject) => {
      const listening = app.listen(0, '127.0.0.1', () => resolve(listening));
      listening.once('error', reject);
    });
    const address = server.address() as AddressInfo;

    try {
      for (const route of RETAINED_READ_ROUTES) {
        const response = await fetch(`http://127.0.0.1:${address.port}${route.path}`);
        assert.equal(response.status, 206, `${backendMode} ${route.path}`);
        assert.match(response.headers.get('content-type') || '', /^application\/json\b/);
        assert.deepEqual(await response.json(), {
          backend: backendMode,
          method: route.method,
          path: route.path,
        });
      }
      const expectedCount = RETAINED_READ_ROUTES.length;
      assert.equal(nodeRequests, backendMode === 'node' ? expectedCount : 0);
      assert.equal(homeAssistantRequests,
        backendMode === 'home_assistant' ? expectedCount : 0);
    } finally {
      await new Promise<void>((resolve, reject) => {
        server.close(error => error ? reject(error) : resolve());
      });
      await service.stop();
    }
  }
});

test('shadow comparison failure cannot alter the real node response', async () => {
  const expectedBody = JSON.stringify([{coordinator: {roomName: 'Synthetic Node'}}]);
  const warnings: string[] = [];
  const nodeRouter = Router();
  nodeRouter.get('/sonos/zones', (_req, res) => {
    res.status(206)
      .setHeader('X-Node-Contract', 'unchanged')
      .type('application/json')
      .send(expectedBody);
  });
  const runtime = {
    start: async () => undefined,
    stop: () => undefined,
    health: () => ({ready: true}),
    zones: () => {
      throw new Error('synthetic HA comparison failure');
    },
  } as unknown as HomeAssistantSonosRuntime;
  const service = createSonosService(config('shadow', 'token'), {
    nodeRouter,
    createNodeReadinessMonitor: () => nodeMonitor(),
    createHomeAssistantRuntime: () => runtime,
    readNodeZones: async () => ({statusCode: 200, body: []}),
    logger: {
      log: () => undefined,
      warn: message => warnings.push(message),
    },
    shadowPollIntervalMs: 0,
  });
  await service.start();
  const app = createApp(service);
  const server = await new Promise<ReturnType<typeof app.listen>>((resolve, reject) => {
    const listening = app.listen(0, '127.0.0.1', () => resolve(listening));
    listening.once('error', reject);
  });
  const address = server.address() as AddressInfo;

  try {
    const response = await fetch(`http://127.0.0.1:${address.port}/sonos/zones`);
    assert.equal(response.status, 206);
    assert.equal(response.headers.get('x-node-contract'), 'unchanged');
    assert.equal(await response.text(), expectedBody);
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(warnings.length, 1);
    assert.equal(JSON.parse(warnings[0]).event, 'sonos_shadow_comparison_failed');
  } finally {
    await new Promise<void>((resolve, reject) => {
      server.close(error => error ? reject(error) : resolve());
    });
    await service.stop();
  }
});

test('shadow mismatch logging waits for the full grace interval and resets on convergence', async () => {
  const member = (volume: number) => ({
    roomName: 'Kitchen',
    state: {
      volume,
      playbackState: 'PLAYING',
      currentTrack: {title: 'Track', artist: 'Artist', album: 'Album', stationName: 'Station'},
    },
  });
  const nodeZones: ShadowZoneLike[] = [{
    coordinator: member(10),
    members: [member(10)],
  }];
  let homeAssistantZones: ShadowZoneLike[] = [{
    coordinator: member(20),
    members: [member(20)],
  }];
  let now = 0;
  let nodeReads = 0;
  const logs: string[] = [];
  const warnings: string[] = [];
  const runtime = {
    zones: () => homeAssistantZones,
  } as unknown as HomeAssistantSonosRuntime;
  const observe = createShadowObserver(runtime, 'http://node.test:5005', {
    now: () => now,
    graceMs: 5_000,
    pollIntervalMs: 5_000,
    readNodeZones: async url => {
      nodeReads += 1;
      assert.equal(url, 'http://node.test:5005/zones');
      return {statusCode: 200, body: nodeZones};
    },
    logger: {
      log: message => logs.push(message),
      warn: message => warnings.push(message),
    },
  });

  await observe();
  assert.equal(nodeReads, 1);
  assert.deepEqual(logs, []);
  assert.deepEqual(warnings, [], 'the initial mismatch is not emitted');

  now = 4_999;
  await observe();
  assert.equal(nodeReads, 1, 'the observer is also rate limited');
  assert.deepEqual(warnings, []);

  now = 5_000;
  await observe();
  assert.equal(nodeReads, 2);
  assert.equal(warnings.length, 1);
  assert.deepEqual(JSON.parse(warnings[0]), {
    event: 'sonos_shadow_persistent_difference',
    equal: false,
    graceMs: 5_000,
    persistentForMs: 5_000,
    differenceCount: 1,
    differences: [{
      kind: 'volume',
      roomName: 'Kitchen',
      nodeValue: 10,
      homeAssistantValue: 20,
    }],
  });

  now = 10_000;
  await observe();
  assert.equal(warnings.length, 1, 'an unchanged persistent mismatch is not re-alerted');

  homeAssistantZones = nodeZones;
  now = 15_000;
  await observe();
  assert.equal(logs.length, 1);
  assert.deepEqual(JSON.parse(logs[0]), {
    event: 'sonos_shadow_comparison',
    equal: true,
    differenceCount: 0,
  });

  homeAssistantZones = [{coordinator: member(25), members: [member(25)]}];
  now = 20_000;
  await observe();
  assert.equal(warnings.length, 1, 'recurrence starts a fresh grace interval');
  now = 25_000;
  await observe();
  assert.equal(warnings.length, 2);
});

test('HA health reports auth, inventory, availability, freshness, and recovery transitions', async () => {
  const stateStore = new MutableHealthStateStore(haSnapshot([], {
    freshness: 'unknown',
    connected: false,
    observedAt: null,
    ageMs: Number.MAX_SAFE_INTEGER,
    lastError: 'Home Assistant WebSocket authentication was rejected',
  }));
  const client: HomeAssistantClientLike = {
    getStates: async () => [],
    connectStateEvents: async () => ({close() {}}),
    callService: async () => ({}),
    fetchAuthenticatedPath: async path => {
      throw new Error(`Bearer synthetic-token failed while fetching ${path}`);
    },
  };
  const runtime = new HomeAssistantSonosRuntime({client, stateStore});
  const service = createSonosService(config('home_assistant', 'synthetic-token'), {
    createHomeAssistantRuntime: () => runtime,
    createNodeReadinessMonitor: () => nodeMonitor(),
  });
  await service.start();
  const app = createApp(service);
  const server = await new Promise<ReturnType<typeof app.listen>>((resolve, reject) => {
    const listening = app.listen(0, '127.0.0.1', () => resolve(listening));
    listening.once('error', reject);
  });
  const address = server.address() as AddressInfo;
  const readHealth = async (): Promise<{
    status: number;
    body: Record<string, any>;
  }> => {
    const response = await fetch(`http://127.0.0.1:${address.port}/health`);
    return {
      status: response.status,
      body: await response.json() as Record<string, any>,
    };
  };

  try {
    const rejected = await readHealth();
    assert.equal(rejected.status, 503);
    assert.equal(rejected.body.ready, false);
    assert.equal(rejected.body.homeAssistant.freshness, 'unknown');
    assert.equal(
      rejected.body.homeAssistant.error,
      'Home Assistant WebSocket authentication was rejected'
    );
    assert.equal(JSON.stringify(rejected.body).includes('synthetic-token'), false);

    stateStore.current = healthSnapshot({missingRoom: 'Office'});
    const missing = await readHealth();
    assert.equal(missing.status, 503);
    assert.deepEqual(missing.body.homeAssistant.missingRooms, ['Office']);
    assert.ok(missing.body.homeAssistant.missingPresetSources.includes('Office-tv:TV'));

    stateStore.current = healthSnapshot({unavailableRoom: 'Office'});
    const unavailable = await readHealth();
    assert.equal(unavailable.status, 503);
    assert.deepEqual(unavailable.body.homeAssistant.missingRooms, []);
    assert.deepEqual(unavailable.body.homeAssistant.unavailableRooms, ['Office']);

    stateStore.current = healthSnapshot({freshness: 'stale'});
    const stale = await readHealth();
    assert.equal(stale.status, 503);
    assert.equal(stale.body.homeAssistant.freshness, 'stale');
    assert.deepEqual(stale.body.homeAssistant.missingRooms, []);
    assert.deepEqual(stale.body.homeAssistant.unavailableRooms, []);

    stateStore.current = healthSnapshot({freshness: 'unknown'});
    const unknown = await readHealth();
    assert.equal(unknown.status, 503);
    assert.equal(unknown.body.homeAssistant.freshness, 'unknown');

    stateStore.current = healthSnapshot();
    const recovered = await readHealth();
    assert.equal(recovered.status, 200);
    assert.deepEqual(recovered.body, {
      status: 'ok',
      ready: true,
      backendMode: 'home_assistant',
      homeAssistant: {
        ready: true,
        freshness: 'live',
        missingRooms: [],
        unavailableRooms: [],
        missingFavorites: [],
        missingPresetSources: [],
      },
    });

    const artworkFailure = await fetch(
      `http://127.0.0.1:${address.port}/sonos/Kitchen/artwork`
    );
    assert.equal(artworkFailure.status, 502);
    const artworkFailureBody = await artworkFailure.json();
    assert.deepEqual(artworkFailureBody, {
      error: 'Home Assistant artwork request failed',
      code: 'artwork_fetch_failed',
      retryable: true,
    });
    assert.equal(JSON.stringify(artworkFailureBody).includes('synthetic-token'), false);
    assert.equal(JSON.stringify(artworkFailureBody).includes('synthetic-health-picture-token'), false);
  } finally {
    await new Promise<void>((resolve, reject) => {
      server.close(error => error ? reject(error) : resolve());
    });
    await service.stop();
  }
});

test('HA mode is non-ready when authentication is not configured', async () => {
  const service = createSonosService(config('home_assistant'));
  await service.start();
  const health = service.health();
  assert.equal(health.statusCode, 503);
  assert.equal(health.body.status, 'not_ready');
  assert.equal(health.body.ready, false);
  assert.equal(health.body.backendMode, 'home_assistant');
  assert.equal(health.body.error, 'SUPERVISOR_TOKEN is required for Home Assistant mode');
  await service.stop();
});

test('health remains reachable before the unavailable router without permissive CORS', async () => {
  const service = createSonosService(config('home_assistant'));
  await service.start();
  const app = createApp(service);
  const server = await new Promise<ReturnType<typeof app.listen>>((resolve, reject) => {
    const listening = app.listen(0, '127.0.0.1', () => resolve(listening));
    listening.once('error', reject);
  });
  const address = server.address() as AddressInfo;

  try {
    const response = await fetch(`http://127.0.0.1:${address.port}/health`, {
      headers: {Origin: 'https://untrusted.example'},
    });
    assert.equal(response.status, 503);
    assert.equal(response.headers.get('access-control-allow-origin'), null);
    assert.deepEqual(await response.json(), {
      status: 'not_ready',
      ready: false,
      backendMode: 'home_assistant',
      error: 'SUPERVISOR_TOKEN is required for Home Assistant mode',
    });
  } finally {
    await new Promise<void>((resolve, reject) => {
      server.close(error => error ? reject(error) : resolve());
    });
    await service.stop();
  }
});
