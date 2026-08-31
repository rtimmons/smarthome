import assert from 'node:assert/strict';
import type {AddressInfo} from 'node:net';
import test from 'node:test';

import express = require('express');

import type {
  HomeAssistantClientLike,
  HomeAssistantEntityState,
  HomeAssistantStateEventHandlers,
} from './home-assistant-client';
import {HomeAssistantSonosActions} from './home-assistant-sonos-actions';
import {
  CONFIGURED_SONOS_FAVORITES,
  createHomeAssistantSonosRouter,
  HomeAssistantSonosRuntime,
  type HomeAssistantSonosStateStore,
} from './home-assistant-sonos-runtime';
import {SonosBackendError, type SonosStateSnapshot} from './sonos-contract';
import {
  SONOS_ROOM_NAMES,
  SONOS_ROOM_TO_ENTITY,
} from './sonos-room-map';

interface RecordedCall {
  domain: string;
  service: string;
  data: Record<string, unknown>;
}

const now = Date.parse('2026-08-28T12:00:00.000Z');
const allEntityIds = SONOS_ROOM_NAMES.map(room => SONOS_ROOM_TO_ENTITY[room]);
const allSources = [...CONFIGURED_SONOS_FAVORITES, 'TV'];

const stateFor = (roomName: (typeof SONOS_ROOM_NAMES)[number]): HomeAssistantEntityState => ({
  entity_id: SONOS_ROOM_TO_ENTITY[roomName],
  state: 'playing',
  attributes: {
    friendly_name: roomName,
    group_members: [...allEntityIds],
    volume_level: 0.2,
    is_volume_muted: false,
    media_title: '#JackedRadio',
    media_artist: '@Afrojack',
    media_album_name: '',
    media_channel: "CH 735 - Steve Aoki's Remix Radio",
    media_content_id: 'x-sonosapi-stream:synthetic',
    media_content_type: 'music',
    media_position: 10,
    media_position_updated_at: '2026-08-28T11:59:55.000Z',
    entity_picture: `/api/media_player_proxy/${SONOS_ROOM_TO_ENTITY[roomName]}?token=synthetic-token`,
    source_list: [...allSources],
  },
  last_changed: '2026-08-28T11:59:00.000Z',
  last_updated: '2026-08-28T11:59:59.000Z',
});

class StaticStateStore implements HomeAssistantSonosStateStore {
  snapshotCalls = 0;
  freshness: SonosStateSnapshot['freshness'] = 'live';
  connected = true;
  ageMs = 0;
  private readonly listeners = new Set<(snapshot: SonosStateSnapshot) => void>();
  readonly entities = new Map<string, HomeAssistantEntityState>(allEntityIds.map(entityId => {
    const room = SONOS_ROOM_NAMES.find(name => SONOS_ROOM_TO_ENTITY[name] === entityId);
    if (!room) throw new Error(`Unknown fixture entity ${entityId}`);
    return [entityId, stateFor(room)];
  }));

  async start(): Promise<void> {}
  stop(): void {}
  subscribe(listener: (snapshot: SonosStateSnapshot) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }
  snapshot(): SonosStateSnapshot {
    this.snapshotCalls += 1;
    return {
      freshness: this.freshness,
      connected: this.connected,
      observedAt: now,
      ageMs: this.ageMs,
      entities: new Map(this.entities),
    };
  }
  notify(): void {
    const snapshot = this.snapshot();
    for (const listener of this.listeners) {
      listener(snapshot);
    }
  }
  assertCommandable(entityIds: readonly string[]): void {
    if (this.freshness !== 'live') {
      throw new SonosBackendError('state_unavailable', 'state unavailable', 503, true);
    }
    for (const entityId of entityIds) {
      const state = this.entities.get(entityId);
      assert.ok(state, `fixture must contain ${entityId}`);
      if (state.state === 'unavailable' || state.state === 'unknown') {
        throw new SonosBackendError('room_unavailable', `${entityId} unavailable`, 503, true);
      }
    }
  }
}

class AlternatingStateStore implements HomeAssistantSonosStateStore {
  snapshotCalls = 0;

  constructor(private readonly snapshots: readonly SonosStateSnapshot[]) {}

  async start(): Promise<void> {}
  stop(): void {}
  subscribe(_listener: (snapshot: SonosStateSnapshot) => void): () => void {
    return () => undefined;
  }
  snapshot(): SonosStateSnapshot {
    const snapshot = this.snapshots[this.snapshotCalls % this.snapshots.length];
    this.snapshotCalls += 1;
    return snapshot;
  }
  assertCommandable(_entityIds: readonly string[]): void {}
}

const snapshotAtVolume = (
  volume: number,
  freshness: SonosStateSnapshot['freshness'],
  observedAt: number,
  ageMs: number
): SonosStateSnapshot => ({
  freshness,
  connected: freshness === 'live',
  observedAt,
  ageMs,
  entities: new Map(SONOS_ROOM_NAMES.map(roomName => {
    const state = stateFor(roomName);
    state.attributes.volume_level = volume;
    return [state.entity_id, state];
  })),
});

const fixture = () => {
  const calls: RecordedCall[] = [];
  const artworkBytes = new Uint8Array([0, 255, 2, 128, 64]);
  const followerArtworkBytes = new Uint8Array([7, 7, 7]);
  const artworkPaths: string[] = [];
  const stateStore = new StaticStateStore();
  const client: HomeAssistantClientLike = {
    getStates: async () => [],
    connectStateEvents: async (_handlers: HomeAssistantStateEventHandlers) => ({close() {}}),
    callService: async (domain, service, data) => {
      calls.push({domain, service, data});
      const entityIds = typeof data.entity_id === 'string'
        ? [data.entity_id]
        : Array.isArray(data.entity_id)
          ? data.entity_id.filter((value): value is string => typeof value === 'string')
          : [];
      if (service === 'unjoin' && entityIds[0]) {
        const state = stateStore.entities.get(entityIds[0]);
        if (state) state.attributes.group_members = [entityIds[0]];
      } else if (service === 'join' && entityIds[0] && Array.isArray(data.group_members)) {
        const members = [
          entityIds[0],
          ...data.group_members.filter((value): value is string => typeof value === 'string'),
        ];
        for (const member of members) {
          const state = stateStore.entities.get(member);
          if (state) state.attributes.group_members = [...members];
        }
      } else if (service === 'volume_set' && entityIds[0]) {
        const state = stateStore.entities.get(entityIds[0]);
        if (state) state.attributes.volume_level = data.volume_level;
      } else if (service === 'select_source' && entityIds[0]) {
        const state = stateStore.entities.get(entityIds[0]);
        if (state) state.attributes.source = data.source;
      } else if (service === 'media_pause') {
        for (const entityId of entityIds) {
          const state = stateStore.entities.get(entityId);
          if (state) state.state = 'paused';
        }
      }
      stateStore.notify();
      return {};
    },
    fetchAuthenticatedPath: async path => {
      artworkPaths.push(path);
      const body = path.startsWith('/api/media_player_proxy/media_player.bathroom')
        ? artworkBytes
        : path.startsWith('/api/media_player_proxy/media_player.kitchen')
          ? followerArtworkBytes
          : assert.fail(`unexpected artwork path ${path}`);
      return new Response(body, {
        status: 200,
        headers: {'Content-Type': 'image/png', 'Content-Length': String(body.length)},
      });
    },
  };
  const runtime = new HomeAssistantSonosRuntime({client, stateStore, now: () => now});
  return {artworkPaths, calls, artworkBytes, followerArtworkBytes, runtime, stateStore};
};

const withServer = async (
  runtime: HomeAssistantSonosRuntime,
  callback: (baseUrl: string) => Promise<void>
): Promise<void> => {
  const app = express();
  app.use(express.json());
  app.use(createHomeAssistantSonosRouter(runtime));
  const server = await new Promise<ReturnType<typeof app.listen>>((resolve, reject) => {
    const listening = app.listen(0, '127.0.0.1', () => resolve(listening));
    listening.once('error', reject);
  });
  const address = server.address() as AddressInfo;
  try {
    await callback(`http://127.0.0.1:${address.port}`);
  } finally {
    await new Promise<void>((resolve, reject) => {
      server.close(error => error ? reject(error) : resolve());
    });
  }
};

test('HA runtime health verifies every room, configured favorite, and TV preset source', () => {
  const {runtime, stateStore} = fixture();
  assert.deepEqual(runtime.health(), {
    ready: true,
    freshness: 'live',
    missingRooms: [],
    unavailableRooms: [],
    missingFavorites: [],
    missingPresetSources: [],
  });
  const kitchen = stateStore.entities.get('media_player.kitchen');
  assert.ok(kitchen);
  kitchen.attributes.source_list = ['TV'];
  const health = runtime.health();
  assert.equal(health.ready, false);
  assert.ok(health.missingFavorites.includes('Kitchen:Rockboat'));

  kitchen.attributes.source_list = [...allSources];
  assert.equal(runtime.health().ready, true,
    'health recovers after Home Assistant reports the corrected source list');
});

test('every configured favorite maps to exactly one Home Assistant source selection', async () => {
  for (const favorite of CONFIGURED_SONOS_FAVORITES) {
    const {calls, runtime} = fixture();
    await withServer(runtime, async baseUrl => {
      const response = await fetch(
        `${baseUrl}/sonos/Kitchen/favorite/${encodeURIComponent(favorite)}`
      );
      assert.equal(response.status, 200, favorite);
      assert.deepEqual(calls, [{
        domain: 'media_player',
        service: 'select_source',
        data: {entity_id: 'media_player.kitchen', source: favorite},
      }], favorite);
    });
  }
});

test('a stale preset request fails closed before any Home Assistant service call', async () => {
  const {calls, runtime, stateStore} = fixture();
  stateStore.freshness = 'stale';
  stateStore.connected = false;

  await withServer(runtime, async baseUrl => {
    const response = await fetch(`${baseUrl}/sonos/Office/preset/Office-tv`);
    assert.equal(response.status, 503);
    assert.equal((await response.json() as {code: string}).code, 'state_unavailable');
    assert.equal(calls.length, 0);
  });
});

test('zones and room-state headers and bodies each derive from one immutable snapshot', async () => {
  const staleObservedAt = now - 1_500;
  const stateStore = new AlternatingStateStore([
    snapshotAtVolume(0.11, 'stale', staleObservedAt, 1_500),
    snapshotAtVolume(0.88, 'live', now, 0),
  ]);
  const client: HomeAssistantClientLike = {
    getStates: async () => [],
    connectStateEvents: async () => ({close() {}}),
    callService: async () => ({}),
    fetchAuthenticatedPath: async () => assert.fail('artwork is not requested'),
  };
  const runtime = new HomeAssistantSonosRuntime({client, stateStore, now: () => now});

  await withServer(runtime, async baseUrl => {
    const zones = await fetch(`${baseUrl}/sonos/zones`);
    assert.equal(zones.status, 200);
    assert.equal(zones.headers.get('x-sonos-response-stale'), 'true');
    assert.equal(zones.headers.get('x-sonos-observed-at'), new Date(staleObservedAt).toISOString());
    assert.equal(zones.headers.get('x-sonos-age-ms'), '1500');
    const zoneBody = await zones.json() as Array<{
      members: Array<{state: {volume: number}}>;
    }>;
    assert.ok(zoneBody[0].members.every(member => member.state.volume === 11),
      'the body uses the same stale snapshot as its freshness headers');
    assert.equal(stateStore.snapshotCalls, 1,
      'zones captures exactly one snapshot for headers and projection');

    const state = await fetch(`${baseUrl}/sonos/Kitchen/state`);
    assert.equal(state.status, 200);
    assert.equal(state.headers.get('x-sonos-response-stale'), 'false');
    assert.equal(state.headers.get('x-sonos-observed-at'), new Date(now).toISOString());
    assert.equal(state.headers.get('x-sonos-age-ms'), '0');
    assert.equal((await state.json() as {volume: number}).volume, 88,
      'the body uses the same live snapshot as its freshness headers');
    assert.equal(stateStore.snapshotCalls, 2,
      'room-state captures exactly one additional snapshot');
  });
});

test('real HA router preserves read, encoded action, validation, and binary artwork contracts', async () => {
  const {
    artworkPaths,
    calls,
    artworkBytes,
    followerArtworkBytes,
    runtime,
    stateStore,
  } = fixture();
  await withServer(runtime, async baseUrl => {
    const zones = await fetch(`${baseUrl}/sonos/zones`);
    assert.equal(zones.status, 200);
    assert.equal(zones.headers.get('x-sonos-response-source'), 'home_assistant');
    assert.equal(zones.headers.get('x-sonos-response-stale'), 'false');
    const zoneBody = await zones.json() as Array<{coordinator: {roomName: string}; members: unknown[]}>;
    assert.equal(zoneBody.length, 1);
    assert.equal(zoneBody[0].coordinator.roomName, 'Bathroom');
    assert.equal(zoneBody[0].members.length, 8);

    const state = await fetch(`${baseUrl}/sonos/Living%20Room/state`);
    assert.equal(state.status, 200);
    const stateBody = await state.json() as {volume: number; currentTrack: {absoluteAlbumArtUri: string}};
    assert.equal(stateBody.volume, 20);
    assert.match(stateBody.currentTrack.absoluteAlbumArtUri,
      /^\.\/sonos\/Living%20Room\/artwork\?rev=[a-z0-9]+$/);
    assert.equal(stateBody.currentTrack.absoluteAlbumArtUri.includes('token='), false);

    const snapshotsBeforeArtwork = stateStore.snapshotCalls;
    const artwork = await fetch(`${baseUrl}/sonos/Kitchen/artwork?rev=safe`);
    assert.equal(artwork.status, 200);
    assert.equal(artwork.headers.get('content-type'), 'image/png');
    assert.equal(artwork.headers.get('x-content-type-options'), 'nosniff');
    assert.deepEqual(new Uint8Array(await artwork.arrayBuffer()), artworkBytes);
    assert.notDeepEqual(artworkBytes, followerArtworkBytes);
    assert.deepEqual(artworkPaths, [
      '/api/media_player_proxy/media_player.bathroom?token=synthetic-token',
    ], 'follower route fetches the coordinator path, never the follower picture');
    assert.equal(
      stateStore.snapshotCalls - snapshotsBeforeArtwork,
      1,
      'artwork freshness headers and authenticated fetch share one snapshot'
    );

    const favorite = "735 - Steve Aoki's Remix Radio";
    const favoriteResponse = await fetch(
      `${baseUrl}/sonos/Guest%20Bathroom/favorite/${encodeURIComponent(favorite)}`
    );
    assert.equal(favoriteResponse.status, 200);
    assert.deepEqual(calls.at(-1), {
      domain: 'media_player',
      service: 'select_source',
      data: {entity_id: 'media_player.guest_bathroom', source: favorite},
    });

    const callsBeforeVolume = calls.length;
    const relative = await fetch(`${baseUrl}/sonos/Living%20Room/groupVolume/%2B2`);
    assert.equal(relative.status, 200);
    assert.equal(calls.length - callsBeforeVolume, 8);
    assert.ok(calls.slice(callsBeforeVolume).every(call =>
      call.service === 'volume_set' && call.data.volume_level === 0.22));

    const callsBeforeNegativeVolume = calls.length;
    const negativeRelative = await fetch(`${baseUrl}/sonos/Living%20Room/groupVolume/%2D5`);
    assert.equal(negativeRelative.status, 200);
    assert.equal(calls.length - callsBeforeNegativeVolume, 8);
    assert.ok(calls.slice(callsBeforeNegativeVolume).every(call =>
      call.service === 'volume_set' && call.data.volume_level === 0.17));

    const callsBeforeFailures = calls.length;
    const invalidRoom = await fetch(`${baseUrl}/sonos/TV%20Room/play`);
    assert.equal(invalidRoom.status, 404);
    assert.equal((await invalidRoom.json() as {code: string}).code, 'unknown_room');
    const invalidFavorite = await fetch(`${baseUrl}/sonos/Kitchen/favorite/Not%20Configured`);
    assert.equal(invalidFavorite.status, 404);
    const invalidDecimal = await fetch(`${baseUrl}/sonos/Kitchen/groupVolume/2.5`);
    assert.equal(invalidDecimal.status, 400);
    const unsupportedMethod = await fetch(`${baseUrl}/sonos/zones`, {method: 'POST'});
    assert.equal(unsupportedMethod.status, 404);
    assert.equal(calls.length, callsBeforeFailures, 'invalid routes make zero HA calls');
  });
});

test('real HA router preserves the frozen group-volume input and clamp matrix', async () => {
  const validCases = [
    {input: '%2B2', expectedVolume: 0.22, description: 'positive relative'},
    {input: '%2D2', expectedVolume: 0.18, description: 'negative relative'},
    {input: '0', expectedVolume: 0, description: 'absolute zero'},
    {input: '100', expectedVolume: 1, description: 'absolute one hundred'},
    {input: '101', expectedVolume: 1, description: 'absolute high clamp'},
    {input: '%2D101', expectedVolume: 0, description: 'relative low clamp'},
  ];

  for (const contract of validCases) {
    const {calls, runtime} = fixture();
    await withServer(runtime, async baseUrl => {
      const response = await fetch(
        `${baseUrl}/sonos/Living%20Room/groupVolume/${contract.input}`
      );
      assert.equal(response.status, 200, contract.description);
      assert.deepEqual(await response.json(), {status: 'success'}, contract.description);
      assert.equal(calls.length, SONOS_ROOM_NAMES.length, contract.description);
      assert.ok(calls.every(call =>
        call.domain === 'media_player' &&
        call.service === 'volume_set' &&
        call.data.volume_level === contract.expectedVolume
      ), contract.description);
    });
  }

  for (const input of ['2.5', 'loud']) {
    const {calls, runtime} = fixture();
    await withServer(runtime, async baseUrl => {
      const response = await fetch(`${baseUrl}/sonos/Kitchen/groupVolume/${input}`);
      assert.equal(response.status, 400, input);
      assert.equal((await response.json() as {code: string}).code, 'invalid_volume', input);
      assert.equal(calls.length, 0, `${input} is rejected before any HA call`);
    });
  }
});

test('real HA router accepts exactly the configured room allowlist', async () => {
  const {calls, runtime} = fixture();
  await withServer(runtime, async baseUrl => {
    for (const roomName of SONOS_ROOM_NAMES) {
      const response = await fetch(
        `${baseUrl}/sonos/${encodeURIComponent(roomName)}/play`
      );
      assert.equal(response.status, 200, roomName);
      assert.deepEqual(calls.at(-1), {
        domain: 'media_player',
        service: 'media_play',
        data: {entity_id: SONOS_ROOM_TO_ENTITY[roomName]},
      }, roomName);
    }

    const callsBeforeInvalidRooms = calls.length;
    const invalidCases = [
      {path: '/sonos//play', code: 'unsupported_route', description: 'empty room'},
      {path: '/sonos/kitchen/play', code: 'unknown_room', description: 'case-changed room'},
      {
        path: '/sonos/%2E%2E%2FKitchen/play',
        code: 'unknown_room',
        description: 'traversal-like room',
      },
      {path: '/sonos/maker_room/play', code: 'unknown_room', description: 'maker_room'},
    ];
    for (const contract of invalidCases) {
      const response = await fetch(`${baseUrl}${contract.path}`);
      assert.equal(response.status, 404, contract.description);
      assert.equal(
        (await response.json() as {code: string}).code,
        contract.code,
        contract.description
      );
    }
    assert.equal(
      calls.length,
      callsBeforeInvalidRooms,
      'invalid room inputs are rejected before any HA call'
    );
  });
});

test('every retained HA route has a frozen success response contract', async () => {
  type ResponseKind =
    'zones' | 'state' | 'artwork' | 'success' | 'operation' | 'intent' | 'status' | 'deprecated';
  const favorite = encodeURIComponent("735 - Steve Aoki's Remix Radio");
  const cases: Array<{
    method: 'GET' | 'POST';
    path: string;
    status: number;
    kind: ResponseKind;
    body?: Record<string, unknown>;
  }> = [
    {method: 'GET', path: '/sonos/zones', status: 200, kind: 'zones'},
    {method: 'GET', path: '/sonos/Guest%20Bathroom/state', status: 200, kind: 'state'},
    {method: 'GET', path: '/sonos/Guest%20Bathroom/artwork', status: 200, kind: 'artwork'},
    {method: 'GET', path: '/sonos/Guest%20Bathroom/play', status: 200, kind: 'success'},
    {method: 'GET', path: '/sonos/Guest%20Bathroom/pause', status: 200, kind: 'success'},
    {method: 'GET', path: '/sonos/Guest%20Bathroom/playpause', status: 200, kind: 'success'},
    {method: 'GET', path: '/sonos/Guest%20Bathroom/next', status: 200, kind: 'success'},
    {
      method: 'GET',
      path: `/sonos/Guest%20Bathroom/favorite/${favorite}`,
      status: 200,
      kind: 'success',
    },
    {
      method: 'GET',
      path: '/sonos/Guest%20Bathroom/join/Living%20Room',
      status: 202,
      kind: 'operation',
    },
    {method: 'GET', path: '/sonos/Guest%20Bathroom/leave', status: 202, kind: 'operation'},
    {
      method: 'GET',
      path: '/sonos/Guest%20Bathroom/groupVolume/%2B2',
      status: 200,
      kind: 'success',
    },
    {
      method: 'GET',
      path: '/sonos/Guest%20Bathroom/volume/12',
      status: 200,
      kind: 'success',
    },
    {
      method: 'GET',
      path: '/sonos/Office/preset/Office-tv',
      status: 202,
      kind: 'operation',
    },
    {method: 'GET', path: '/same/Guest%20Bathroom', status: 200, kind: 'success'},
    {method: 'GET', path: '/up', status: 200, kind: 'success'},
    {method: 'GET', path: '/down', status: 200, kind: 'success'},
    {
      method: 'POST',
      path: '/sonos-intents/group-all',
      status: 202,
      kind: 'intent',
      body: {targetRoom: 'Bathroom', roomNames: [...SONOS_ROOM_NAMES]},
    },
    {method: 'GET', path: '/sonos-intents/status', status: 200, kind: 'status'},
    {method: 'GET', path: '/pause', status: 410, kind: 'deprecated'},
    {method: 'GET', path: '/play', status: 410, kind: 'deprecated'},
    {method: 'GET', path: '/tv', status: 410, kind: 'deprecated'},
    {method: 'GET', path: '/07', status: 410, kind: 'deprecated'},
    {method: 'GET', path: '/quiet', status: 410, kind: 'deprecated'},
  ];

  for (const contract of cases) {
    const {artworkBytes, runtime} = fixture();
    await withServer(runtime, async baseUrl => {
      const response = await fetch(`${baseUrl}${contract.path}`, {
        method: contract.method,
        ...(contract.body
          ? {
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(contract.body),
          }
          : {}),
      });
      assert.equal(response.status, contract.status, contract.path);
      if (contract.kind === 'artwork') {
        assert.equal(response.headers.get('content-type'), 'image/png');
        assert.equal(response.headers.get('x-content-type-options'), 'nosniff');
        assert.deepEqual(new Uint8Array(await response.arrayBuffer()), artworkBytes);
      } else {
        assert.match(response.headers.get('content-type') || '', /^application\/json\b/);
        const body: any = await response.json();
        if (contract.kind === 'zones') {
          assert.ok(Array.isArray(body));
          assert.equal(body.length, 1);
          assert.equal(body[0].coordinator.roomName, 'Bathroom');
          assert.equal(body[0].members.length, SONOS_ROOM_NAMES.length);
        } else if (contract.kind === 'state') {
          assert.deepEqual(Object.keys(body).sort(), [
            'currentTrack', 'elapsedTime', 'elapsedTimeFormatted', 'equalizer', 'mute',
            'nextTrack', 'playMode', 'playbackState', 'sub', 'trackNo', 'volume',
          ]);
        } else if (contract.kind === 'success') {
          assert.deepEqual(body, {status: 'success'});
        } else if (contract.kind === 'operation') {
          assert.deepEqual(Object.keys(body), ['operation']);
          assert.equal(typeof body.operation.id, 'string');
          assert.ok(['queued', 'running'].includes(body.operation.status));
        } else if (contract.kind === 'intent') {
          assert.deepEqual(Object.keys(body), ['intent']);
          assert.equal(body.intent.kind, 'group_all_to_room');
          assert.equal(typeof body.intent.id, 'string');
        } else if (contract.kind === 'status') {
          assert.deepEqual(body, {
            activeIntent: null,
            recentIntent: null,
            serverTime: new Date(now).toISOString(),
          });
        } else {
          assert.equal(body.code, 'deprecated_route');
          assert.equal(typeof body.error, 'string');
        }
      }
      const hasFreshness = ['zones', 'state', 'artwork'].includes(contract.kind);
      assert.equal(
        response.headers.get('x-sonos-response-source'),
        hasFreshness ? 'home_assistant' : null,
        `${contract.path} freshness source`
      );
      assert.equal(
        response.headers.get('x-sonos-response-stale'),
        hasFreshness ? 'false' : null,
        `${contract.path} freshness status`
      );
    });
  }
});

test('every parameterized HA route family has a normalized failure contract', async () => {
  const cases: Array<{
    method?: 'GET' | 'POST';
    path: string;
    status: number;
    code: string;
    body?: Record<string, unknown>;
  }> = [
    {path: '/sonos/Not%20A%20Room/state', status: 404, code: 'unknown_room'},
    {path: '/sonos/Not%20A%20Room/artwork', status: 404, code: 'unknown_room'},
    {path: '/sonos/Not%20A%20Room/play', status: 404, code: 'unknown_room'},
    {path: '/sonos/Not%20A%20Room/pause', status: 404, code: 'unknown_room'},
    {path: '/sonos/Not%20A%20Room/playpause', status: 404, code: 'unknown_room'},
    {path: '/sonos/Not%20A%20Room/next', status: 404, code: 'unknown_room'},
    {
      path: '/sonos/Kitchen/favorite/Not%20Configured',
      status: 404,
      code: 'unknown_favorite',
    },
    {
      path: '/sonos/Kitchen/join/Not%20A%20Room',
      status: 404,
      code: 'unknown_room',
    },
    {path: '/sonos/Not%20A%20Room/leave', status: 404, code: 'unknown_room'},
    {
      path: '/sonos/Kitchen/groupVolume/not-a-number',
      status: 400,
      code: 'invalid_volume',
    },
    {path: '/sonos/Kitchen/volume/nope', status: 400, code: 'invalid_volume'},
    {
      path: '/sonos/Kitchen/preset/Not%20Configured',
      status: 404,
      code: 'unknown_preset',
    },
    {path: '/same/Not%20A%20Room', status: 404, code: 'unknown_room'},
    {
      method: 'POST',
      path: '/intents/sonos/group-all',
      status: 400,
      code: 'invalid_request',
      body: {targetRoom: 'Kitchen', roomNames: []},
    },
    {
      method: 'POST',
      path: '/sonos-intents/group-all',
      status: 400,
      code: 'invalid_request',
      body: {targetRoom: 'Kitchen', roomNames: ['Kitchen', 'Kitchen']},
    },
    {method: 'POST', path: '/sonos/zones', status: 404, code: 'unsupported_route'},
  ];
  const {calls, runtime} = fixture();
  await withServer(runtime, async baseUrl => {
    for (const contract of cases) {
      const response = await fetch(`${baseUrl}${contract.path}`, {
        method: contract.method || 'GET',
        ...(contract.body
          ? {
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(contract.body),
          }
          : {}),
      });
      assert.equal(response.status, contract.status, contract.path);
      assert.match(response.headers.get('content-type') || '', /^application\/json\b/);
      const body = await response.json() as Record<string, unknown>;
      assert.equal(body.code, contract.code, contract.path);
      assert.equal(typeof body.error, 'string', contract.path);
      assert.ok(Object.keys(body).every(key => ['error', 'code', 'retryable'].includes(key)));
      assert.equal(JSON.stringify(body).includes('synthetic-token'), false);
    }
    assert.equal(calls.length, 0, 'normalized invalid-input failures make zero HA calls');
  });
});

test('topology, preset, status, and retained convenience policies are explicit', async () => {
  const {calls, runtime, stateStore} = fixture();
  await withServer(runtime, async baseUrl => {
    const join = await fetch(`${baseUrl}/sonos/Kitchen/join/Living%20Room`);
    assert.equal(join.status, 202);
    const joinBody = await join.json() as {operation: {id: string}};
    assert.ok(joinBody.operation.id);
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(calls.length, 0, 'already-satisfied join is idempotent');

    const groupAll = await fetch(`${baseUrl}/intents/sonos/group-all`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({targetRoom: 'Bathroom', roomNames: [...SONOS_ROOM_NAMES]}),
    });
    assert.equal(groupAll.status, 202);
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(calls.length, 0, 'already-satisfied join-all is idempotent');

    const browserGroupAllAlias = await fetch(`${baseUrl}/sonos-intents/group-all`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({targetRoom: 'Bathroom', roomNames: [...SONOS_ROOM_NAMES]}),
    });
    assert.equal(browserGroupAllAlias.status, 202);
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(calls.length, 0, 'both intent namespaces preserve idempotency');

    const invalidGroupInputs: Array<{
      body: Record<string, unknown>;
      status: number;
      code: string;
    }> = [
      {body: {targetRoom: 'Bathroom'}, status: 400, code: 'invalid_request'},
      {body: {targetRoom: 'Bathroom', roomNames: []}, status: 400, code: 'invalid_request'},
      {
        body: {targetRoom: 'Bathroom', roomNames: ['Bathroom', 'Bathroom']},
        status: 400,
        code: 'invalid_request',
      },
      {
        body: {targetRoom: 'Bathroom', roomNames: ['Kitchen']},
        status: 400,
        code: 'invalid_request',
      },
      {
        body: {targetRoom: 'bathroom', roomNames: ['Bathroom']},
        status: 404,
        code: 'unknown_room',
      },
      {
        body: {targetRoom: 'Bathroom', roomNames: ['Bathroom', 'Maker Room']},
        status: 400,
        code: 'invalid_request',
      },
    ];
    for (const invalid of invalidGroupInputs) {
      for (const path of ['/intents/sonos/group-all', '/sonos-intents/group-all']) {
        const invalidGroup = await fetch(`${baseUrl}${path}`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(invalid.body),
        });
        assert.equal(invalidGroup.status, invalid.status);
        assert.equal((await invalidGroup.json() as {code: string}).code, invalid.code);
      }
    }
    const bathroomState = stateStore.entities.get(SONOS_ROOM_TO_ENTITY.Bathroom);
    assert.ok(bathroomState);
    bathroomState.state = 'unavailable';
    const unavailableTarget = await fetch(`${baseUrl}/intents/sonos/group-all`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({targetRoom: 'Bathroom', roomNames: ['Bathroom']}),
    });
    assert.equal(unavailableTarget.status, 503);
    assert.equal((await unavailableTarget.json() as {code: string}).code, 'room_unavailable');
    bathroomState.state = 'playing';
    assert.equal(calls.length, 0, 'invalid join-all inputs make zero HA calls');

    const preset = await fetch(`${baseUrl}/sonos/Office/preset/Office-tv`);
    assert.equal(preset.status, 202);
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(calls.map(call => call.service), ['unjoin', 'volume_set', 'select_source']);

    const status = await fetch(`${baseUrl}/intents/sonos/status`);
    assert.equal(status.status, 200);
    const statusBody = await status.json() as {recentIntent: {id: string; status: string}};
    assert.ok(statusBody.recentIntent.id);
    assert.equal(statusBody.recentIntent.status, 'completed');

    const browserStatusAlias = await fetch(`${baseUrl}/sonos-intents/status`);
    assert.equal(browserStatusAlias.status, 200);

    for (const path of ['/pause', '/play', '/tv', '/07', '/quiet']) {
      const deprecated = await fetch(`${baseUrl}${path}`);
      assert.equal(deprecated.status, 410, `${path} remains explicitly deprecated`);
      assert.equal((await deprecated.json() as {code: string}).code, 'deprecated_route');
    }

    const callsBeforeUp = calls.length;
    const up = await fetch(`${baseUrl}/up`);
    assert.equal(up.status, 200);
    assert.equal(calls.length - callsBeforeUp, 8,
      'up applies one volume call per current group member');

    const callsBeforeDown = calls.length;
    const down = await fetch(`${baseUrl}/down`);
    assert.equal(down.status, 200);
    assert.equal(calls.length - callsBeforeDown, 8,
      'down applies one volume call per current group member');
  });
});

test('zones omit an unavailable portable room when no reachable group claims it', async () => {
  const {runtime, stateStore} = fixture();
  for (const [entityId, state] of stateStore.entities) {
    state.attributes.group_members = [entityId];
  }
  const office = stateStore.entities.get(SONOS_ROOM_TO_ENTITY.Office);
  assert.ok(office);
  office.state = 'unavailable';

  await withServer(runtime, async baseUrl => {
    const response = await fetch(`${baseUrl}/sonos/zones`);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get('x-sonos-unavailable-rooms'), 'Office');
    const zones = await response.json() as Array<{members: Array<{roomName: string}>}>;
    assert.equal(zones.length, SONOS_ROOM_NAMES.length - 1);
    assert.ok(zones.every(zone => zone.members.every(member => member.roomName !== 'Office')));
  });
});

test('zones omit an unavailable room still claimed by a reachable group', async () => {
  const {runtime, stateStore} = fixture();
  const office = stateStore.entities.get(SONOS_ROOM_TO_ENTITY.Office);
  assert.ok(office);
  office.state = 'unavailable';

  await withServer(runtime, async baseUrl => {
    const response = await fetch(`${baseUrl}/sonos/zones`);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get('x-sonos-unavailable-rooms'), 'Office');
    const zones = await response.json() as Array<{members: Array<{roomName: string}>}>;
    assert.equal(zones.length, 1);
    assert.equal(zones[0].members.length, SONOS_ROOM_NAMES.length - 1);
    assert.ok(zones[0].members.every(member => member.roomName !== 'Office'));
  });
});

test('artwork revision follows coordinator media identity, not volume or signed URL churn', () => {
  const {runtime, stateStore} = fixture();
  const before = runtime.roomState('Living Room') as {
    currentTrack: {absoluteAlbumArtUri: string};
  };
  const follower = stateStore.entities.get(SONOS_ROOM_TO_ENTITY['Living Room']);
  const coordinator = stateStore.entities.get(SONOS_ROOM_TO_ENTITY.Bathroom);
  assert.ok(follower);
  assert.ok(coordinator);

  follower.attributes.entity_picture =
    `/api/media_player_proxy/${SONOS_ROOM_TO_ENTITY['Living Room']}/alternate?token=follower-token`;
  follower.attributes.media_title = 'Follower-only media noise';
  const followerChanged = runtime.roomState('Living Room') as {
    currentTrack: {absoluteAlbumArtUri: string};
  };
  assert.equal(
    followerChanged.currentTrack.absoluteAlbumArtUri,
    before.currentTrack.absoluteAlbumArtUri,
    'a grouped follower cannot take ownership of its artwork revision'
  );

  coordinator.attributes.volume_level = 0.73;
  coordinator.attributes.entity_picture =
    `/api/media_player_proxy/${SONOS_ROOM_TO_ENTITY.Bathroom}?token=rotated-token`;
  coordinator.last_updated = '2026-08-28T12:00:01.000Z';

  const volumeOnly = runtime.roomState('Living Room') as {
    currentTrack: {absoluteAlbumArtUri: string};
  };
  assert.equal(
    volumeOnly.currentTrack.absoluteAlbumArtUri,
    before.currentTrack.absoluteAlbumArtUri
  );

  coordinator.attributes.entity_picture =
    `/api/media_player_proxy/${SONOS_ROOM_TO_ENTITY.Bathroom}/alternate?token=rotated-token`;
  const coordinatorArtworkChanged = runtime.roomState('Living Room') as {
    currentTrack: {absoluteAlbumArtUri: string};
  };
  assert.notEqual(
    coordinatorArtworkChanged.currentTrack.absoluteAlbumArtUri,
    before.currentTrack.absoluteAlbumArtUri,
    'the coordinator artwork path owns the grouped follower revision'
  );

  coordinator.attributes.media_title = 'A different track';
  const mediaChanged = runtime.roomState('Living Room') as {
    currentTrack: {absoluteAlbumArtUri: string};
  };
  assert.notEqual(
    mediaChanged.currentTrack.absoluteAlbumArtUri,
    coordinatorArtworkChanged.currentTrack.absoluteAlbumArtUri,
    'coordinator media identity changes also rotate the revision'
  );
});

test('status exposes the newest queued intent over its superseded active predecessor', async () => {
  const {runtime} = fixture();
  let releaseActive!: () => void;
  const activeGate = new Promise<void>(resolve => {
    releaseActive = resolve;
  });
  const first = runtime.actions.operationQueue.enqueue({
    kind: 'join_all',
    key: 'first',
    targetRoom: 'Bathroom',
    requestedRooms: ['Bathroom', 'Kitchen'],
    run: async () => activeGate,
  });
  await new Promise(resolve => setImmediate(resolve));
  const second = runtime.actions.operationQueue.enqueue({
    kind: 'leave',
    key: 'second',
    requestedRooms: ['Office'],
    run: async () => undefined,
  });

  const status = runtime.status() as {
    activeIntent: {id: string; status: string};
  };
  assert.equal(status.activeIntent.id, second.operation.id);
  assert.equal(status.activeIntent.status, 'queued');

  releaseActive();
  await first.finished;
  await second.finished;
});

test('preset completes only after authoritative coordinator, members, source, and volumes converge', async () => {
  const calls: RecordedCall[] = [];
  const stateStore = new StaticStateStore();
  const office = stateStore.entities.get(SONOS_ROOM_TO_ENTITY.Office);
  assert.ok(office);
  office.attributes.volume_level = 0.1;
  const client: HomeAssistantClientLike = {
    getStates: async () => [],
    connectStateEvents: async () => ({close() {}}),
    callService: async (domain, service, data) => {
      calls.push({domain, service, data});
      return {};
    },
    fetchAuthenticatedPath: async () => new Response(new Uint8Array()),
  };
  const runtime = new HomeAssistantSonosRuntime({client, stateStore, now: () => now});
  const operation = runtime.applyPreset('Office-tv');
  await new Promise(resolve => setImmediate(resolve));

  assert.deepEqual(calls.map(call => call.service), ['unjoin', 'volume_set', 'select_source']);
  assert.equal(runtime.actions.operationQueue.getOperation(operation.id)?.status, 'running');

  office.attributes.source = 'TV';
  stateStore.notify();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(runtime.actions.operationQueue.getOperation(operation.id)?.status, 'running');

  office.attributes.group_members = [SONOS_ROOM_TO_ENTITY.Office];
  stateStore.notify();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(runtime.actions.operationQueue.getOperation(operation.id)?.status, 'running');

  office.attributes.volume_level = 0.2;
  stateStore.notify();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(runtime.actions.operationQueue.getOperation(operation.id)?.status, 'completed');
  runtime.stop();
});

test('preset failure status exposes the failed step and sanitized observed topology', async () => {
  const stateStore = new StaticStateStore();
  let callCount = 0;
  const client: HomeAssistantClientLike = {
    getStates: async () => [],
    connectStateEvents: async () => ({close() {}}),
    callService: async () => {
      callCount += 1;
      if (callCount === 2) {
        throw new Error('synthetic service failure');
      }
      return {};
    },
    fetchAuthenticatedPath: async () => new Response(new Uint8Array()),
  };
  const runtime = new HomeAssistantSonosRuntime({client, stateStore});
  const operation = runtime.applyPreset('Bedroom-tv');
  await new Promise(resolve => setImmediate(resolve));
  await new Promise(resolve => setImmediate(resolve));

  const terminal = runtime.actions.operationQueue.getOperation(operation.id);
  assert.equal(terminal?.status, 'failed');
  assert.equal(terminal?.failedStep, 'join_members:Bedroom');
  assert.ok(terminal?.observedTopology?.some(group =>
    group.coordinator === 'Bathroom' && group.members.includes('Bedroom')
  ));
  assert.doesNotMatch(JSON.stringify(terminal), /media_player\.|RINCON|token/i,
    'failure details contain room labels only');
  runtime.stop();
});

test('pauseOthers preset waits for every non-member to be authoritatively paused', async () => {
  const stateStore = new StaticStateStore();
  const client: HomeAssistantClientLike = {
    getStates: async () => [],
    connectStateEvents: async () => ({close() {}}),
    callService: async () => ({}),
    fetchAuthenticatedPath: async () => new Response(new Uint8Array()),
  };
  const runtime = new HomeAssistantSonosRuntime({client, stateStore});
  const operation = runtime.applyPreset('Living Room-tv');
  await new Promise(resolve => setImmediate(resolve));

  const members = ['Living Room', 'Kitchen', 'Guest Bathroom'] as const;
  const memberIds = members.map(room => SONOS_ROOM_TO_ENTITY[room]);
  for (const room of members) {
    const state = stateStore.entities.get(SONOS_ROOM_TO_ENTITY[room]);
    assert.ok(state);
    state.attributes.group_members = memberIds;
    state.attributes.volume_level = 0.3;
  }
  const coordinator = stateStore.entities.get(SONOS_ROOM_TO_ENTITY['Living Room']);
  assert.ok(coordinator);
  coordinator.attributes.source = 'TV';
  stateStore.notify();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(runtime.actions.operationQueue.getOperation(operation.id)?.status, 'running');

  for (const room of ['Bathroom', 'Closet', 'Bedroom', 'Move', 'Office'] as const) {
    const state = stateStore.entities.get(SONOS_ROOM_TO_ENTITY[room]);
    assert.ok(state);
    state.state = 'paused';
  }
  stateStore.notify();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(runtime.actions.operationQueue.getOperation(operation.id)?.status, 'completed');
  runtime.stop();
});

test('superseding a preset during a service call prevents every later preset write', async () => {
  const calls: RecordedCall[] = [];
  const stateStore = new StaticStateStore();
  let releaseFirstCall!: () => void;
  let markFirstCallStarted!: () => void;
  const firstCallStarted = new Promise<void>(resolve => {
    markFirstCallStarted = resolve;
  });
  const firstCallGate = new Promise<void>(resolve => {
    releaseFirstCall = resolve;
  });
  const client: HomeAssistantClientLike = {
    getStates: async () => [],
    connectStateEvents: async () => ({close() {}}),
    callService: async (domain, service, data) => {
      calls.push({domain, service, data});
      if (calls.length === 1) {
        markFirstCallStarted();
        await firstCallGate;
      }
      return {};
    },
    fetchAuthenticatedPath: async () => new Response(new Uint8Array()),
  };
  const runtime = new HomeAssistantSonosRuntime({client, stateStore});
  const preset = runtime.applyPreset('Office-tv');
  await firstCallStarted;
  const replacement = runtime.actions.operationQueue.enqueue({
    kind: 'leave',
    key: 'manual-replacement',
    requestedRooms: ['Kitchen'],
    run: async () => undefined,
  });
  releaseFirstCall();
  await replacement.finished;

  assert.equal(calls.length, 1, 'the in-flight step finishes but no subsequent step starts');
  assert.equal(runtime.actions.operationQueue.getOperation(preset.id)?.status, 'superseded');
  runtime.stop();
});

test('preset convergence consumes the operation acceptance deadline and times out', async () => {
  let clock = 0;
  const timers: Array<{callback: () => void; dueAt: number; cleared: boolean}> = [];
  const fakeSetTimeout = ((callback: () => void, delay = 0) => {
    const timer = {callback, dueAt: clock + Number(delay), cleared: false};
    timers.push(timer);
    return timer as any;
  }) as typeof setTimeout;
  const fakeClearTimeout = ((timer: any) => {
    timer.cleared = true;
  }) as typeof clearTimeout;
  const calls: RecordedCall[] = [];
  const stateStore = new StaticStateStore();
  const client: HomeAssistantClientLike = {
    getStates: async () => [],
    connectStateEvents: async () => ({close() {}}),
    callService: async (domain, service, data) => {
      calls.push({domain, service, data});
      return {};
    },
    fetchAuthenticatedPath: async () => new Response(new Uint8Array()),
  };
  const actions = new HomeAssistantSonosActions({
    client,
    stateStore,
    topologyDeadlineMs: 20,
    now: () => clock,
    setTimeout: fakeSetTimeout,
    clearTimeout: fakeClearTimeout,
  });
  const runtime = new HomeAssistantSonosRuntime({
    client,
    stateStore,
    actions,
    now: () => clock,
    setTimeout: fakeSetTimeout,
    clearTimeout: fakeClearTimeout,
  });
  const operation = runtime.applyPreset('Office-tv');
  assert.equal(operation.deadlineAt - operation.createdAt, 20);
  await new Promise(resolve => setImmediate(resolve));
  await new Promise(resolve => setImmediate(resolve));
  clock = 20;
  for (const timer of timers.filter(candidate => !candidate.cleared && candidate.dueAt <= clock)) {
    timer.callback();
  }
  await new Promise(resolve => setImmediate(resolve));

  const terminal = runtime.actions.operationQueue.getOperation(operation.id);
  assert.equal(terminal?.status, 'timed_out');
  assert.match(terminal?.error || '', /acceptance deadline|operation deadline/);
  assert.equal(calls.length, 3, 'deadline observation never resubmits a preset service call');
  runtime.stop();
});
