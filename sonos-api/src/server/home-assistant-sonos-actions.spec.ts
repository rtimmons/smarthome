import {strict as assert} from 'assert';

import {
  HomeAssistantClientError,
  HomeAssistantEntityState,
} from './home-assistant-client';
import {HomeAssistantSonosActions, SonosActionStateStore} from './home-assistant-sonos-actions';
import {deferred, haSnapshot, haState, nextTurn} from './home-assistant-test-fixtures';
import {SonosBackendError, SonosStateSnapshot} from './sonos-contract';
import {SONOS_ROOM_TO_ENTITY} from './sonos-room-map';

class FakeStore implements SonosActionStateStore {
  current: SonosStateSnapshot;
  private readonly listeners = new Set<(snapshot: SonosStateSnapshot) => void>();

  constructor(states: HomeAssistantEntityState[]) {
    this.current = haSnapshot(states);
  }

  snapshot(): SonosStateSnapshot {
    return this.current;
  }

  assertCommandable(entityIds: readonly string[]): void {
    if (this.current.freshness !== 'live') {
      throw new SonosBackendError('state_unavailable', 'state unavailable', 503);
    }
    for (const entityId of entityIds) {
      const state = this.current.entities.get(entityId);
      if (!state || state.state === 'unavailable' || state.state === 'unknown') {
        throw new SonosBackendError('room_unavailable', `${entityId} unavailable`, 503);
      }
    }
  }

  subscribe(listener: (snapshot: SonosStateSnapshot) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  set(states: HomeAssistantEntityState[]): void {
    this.current = haSnapshot(states);
    for (const listener of this.listeners) {
      listener(this.current);
    }
  }
}

type Call = {service: string; data: Record<string, unknown>};

const run = async (): Promise<void> => {
  {
    const calls: Call[] = [];
    const store = new FakeStore([haState('Kitchen', {
      attributes: {source_list: ['Zero 7 Radio']},
    })]);
    const actions = new HomeAssistantSonosActions({
      stateStore: store,
      client: {
        async callService(_domain, service, data) {
          calls.push({service, data});
          return {};
        },
      },
    });
    await actions.play('Kitchen');
    await actions.pause('Kitchen');
    await actions.playPause('Kitchen');
    await actions.next('Kitchen');
    await actions.favorite('Kitchen', 'Zero 7 Radio');
    assert.deepEqual(calls, [
      {service: 'media_play', data: {entity_id: 'media_player.kitchen'}},
      {service: 'media_pause', data: {entity_id: 'media_player.kitchen'}},
      {service: 'media_play_pause', data: {entity_id: 'media_player.kitchen'}},
      {service: 'media_next_track', data: {entity_id: 'media_player.kitchen'}},
      {service: 'select_source', data: {
        entity_id: 'media_player.kitchen', source: 'Zero 7 Radio',
      }},
    ]);
    await assert.rejects(actions.favorite('Kitchen', 'Unknown'), /not available/);
    assert.equal(calls.length, 5, 'invalid favorites make no service call');
  }

  {
    const calls: Call[] = [];
    const sources = [
      '735 - Steve Aoki\'s Remix Radio',
      'Apple Music playlist',
      'TV',
      'Line-in',
    ];
    const store = new FakeStore([haState('Kitchen', {
      attributes: {source_list: sources},
    })]);
    const actions = new HomeAssistantSonosActions({
      stateStore: store,
      client: {
        async callService(_domain, service, data) {
          calls.push({service, data});
          return {};
        },
      },
    });
    for (const source of sources) {
      await actions.favorite('Kitchen', source);
    }
    assert.deepEqual(calls, sources.map(source => ({
      service: 'select_source',
      data: {entity_id: 'media_player.kitchen', source},
    })),
    'radio, Apple Music favorite, TV, and Line-in all use exact observed source names');
    await assert.rejects(
      actions.favorite('Kitchen', 'apple music playlist'),
      /not available/
    );
    assert.equal(calls.length, sources.length,
      'case-changed source names are rejected before any Home Assistant call');
  }

  {
    const calls: Call[] = [];
    const store = new FakeStore([
      haState('Bedroom', {
        attributes: {source_list: ['Synthetic Radio']},
      }),
      haState('Kitchen'),
    ]);
    store.current = {
      ...store.current,
      freshness: 'stale',
      connected: false,
      ageMs: 0,
    };
    const actions = new HomeAssistantSonosActions({
      stateStore: store,
      client: {
        async callService(_domain, service, data) {
          calls.push({service, data});
          return {};
        },
      },
    });
    const rejectedPromises = [
      actions.play('Bedroom'),
      actions.favorite('Bedroom', 'Synthetic Radio'),
      actions.groupVolume('Bedroom', '+1'),
      actions.normalizeGroupVolume('Bedroom'),
      actions.setRoomVolume('Bedroom', 20),
    ];
    for (const rejected of rejectedPromises) {
      await assert.rejects(rejected, /state unavailable/);
    }
    for (const topology of [
      () => actions.join('Kitchen', 'Bedroom'),
      () => actions.leave('Bedroom'),
      () => actions.joinAll('Bedroom', ['Bedroom', 'Kitchen']),
    ]) {
      assert.throws(topology, /state unavailable/);
    }
    assert.equal(calls.length, 0,
      'playback, favorite, volume, and topology writes all fail closed at disconnect age zero');
  }

  {
    const calls: Call[] = [];
    const initial = [
      haState('Bedroom', {members: ['Bedroom', 'Office']}),
      haState('Office', {members: ['Bedroom', 'Office']}),
      haState('Kitchen'),
    ];
    const store = new FakeStore(initial);
    const actions = new HomeAssistantSonosActions({
      stateStore: store,
      client: {
        async callService(_domain, service, data) {
          calls.push({service, data});
          store.set([
            haState('Bedroom', {members: ['Bedroom', 'Office', 'Kitchen']}),
            haState('Office', {members: ['Bedroom', 'Kitchen', 'Office']}),
            haState('Kitchen', {members: ['Bedroom', 'Office', 'Kitchen']}),
          ]);
          return {};
        },
      },
    });
    const operation = actions.join('Kitchen', 'Office');
    assert.equal((await operation.finished).status, 'completed');
    assert.deepEqual(calls, [{
      service: 'join',
      data: {
        entity_id: 'media_player.bedroom',
        group_members: ['media_player.kitchen'],
      },
    }], 'manual join targets the destination group coordinator exactly once');
    assert.equal((await operation.finished).serviceCallCount, 1);
  }

  {
    const calls: Call[] = [];
    const store = new FakeStore([
      haState('Bedroom', {members: ['Bedroom', 'Kitchen']}),
      haState('Kitchen', {members: ['Bedroom', 'Kitchen']}),
    ]);
    const actions = new HomeAssistantSonosActions({
      stateStore: store,
      client: {
        async callService(_domain, service, data) {
          calls.push({service, data});
          return {};
        },
      },
    });

    const selfJoin = await actions.join('Bedroom', 'Bedroom').finished;
    const alreadyJoined = await actions.join('Kitchen', 'Bedroom').finished;
    assert.equal(selfJoin.status, 'completed');
    assert.equal(selfJoin.serviceCallCount, 0);
    assert.equal(alreadyJoined.status, 'completed');
    assert.equal(alreadyJoined.serviceCallCount, 0);
    assert.equal(calls.length, 0,
      'self-join and joining an already-observed member are idempotent without writes');
  }

  {
    const calls: Call[] = [];
    const store = new FakeStore([
      haState('Bedroom', {members: ['Bedroom', 'Kitchen']}),
      haState('Kitchen', {members: ['Bedroom', 'Kitchen']}),
      haState('Office'),
    ]);
    const actions = new HomeAssistantSonosActions({
      stateStore: store,
      client: {
        async callService(_domain, service, data) {
          calls.push({service, data});
          store.set([
            haState('Bedroom'),
            haState('Office', {members: ['Office', 'Kitchen']}),
            haState('Kitchen', {members: ['Office', 'Kitchen']}),
          ]);
          return {};
        },
      },
    });

    const moved = await actions.join('Kitchen', 'Office').finished;
    assert.equal(moved.status, 'completed');
    assert.equal(moved.serviceCallCount, 1);
    assert.deepEqual(calls, [{
      service: 'join',
      data: {
        entity_id: SONOS_ROOM_TO_ENTITY.Office,
        group_members: [SONOS_ROOM_TO_ENTITY.Kitchen],
      },
    }], 'moving a room submits one join to the destination coordinator');
  }

  {
    const calls: Call[] = [];
    const store = new FakeStore([
      haState('Bedroom', {members: ['Bedroom', 'Kitchen']}),
      haState('Kitchen', {members: ['Bedroom', 'Kitchen']}),
    ]);
    const actions = new HomeAssistantSonosActions({
      stateStore: store,
      client: {
        async callService(_domain, service, data) {
          calls.push({service, data});
          store.set([
            haState('Bedroom'),
            haState('Kitchen'),
          ]);
          return {};
        },
      },
    });

    const coordinatorLeave = await actions.leave('Bedroom').finished;
    assert.equal(coordinatorLeave.status, 'completed');
    assert.equal(coordinatorLeave.serviceCallCount, 1);
    assert.deepEqual(calls, [{
      service: 'unjoin',
      data: {entity_id: SONOS_ROOM_TO_ENTITY.Bedroom},
    }], 'leaving through the coordinator targets that coordinator exactly once');
  }

  {
    const calls: Call[] = [];
    const store = new FakeStore([
      haState('Bedroom'),
      haState('Kitchen', {state: 'unavailable'}),
    ]);
    const actions = new HomeAssistantSonosActions({
      stateStore: store,
      client: {
        async callService(_domain, service, data) {
          calls.push({service, data});
          return {};
        },
      },
    });

    assert.throws(
      () => actions.join('Kitchen', 'Bedroom'),
      (error: unknown) => error instanceof SonosBackendError &&
        error.code === 'room_unavailable'
    );
    store.set([
      haState('Bedroom', {state: 'unavailable'}),
      haState('Kitchen'),
    ]);
    assert.throws(
      () => actions.join('Kitchen', 'Bedroom'),
      (error: unknown) => error instanceof SonosBackendError &&
        error.code === 'room_unavailable'
    );
    assert.equal(calls.length, 0,
      'an unavailable source or destination anchor is rejected before any write');
  }

  {
    const calls: Call[] = [];
    const store = new FakeStore([haState('Kitchen')]);
    const actions = new HomeAssistantSonosActions({
      stateStore: store,
      client: {
        async callService(_domain, service, data) {
          calls.push({service, data});
          return {};
        },
      },
    });
    assert.equal((await actions.leave('Kitchen').finished).status, 'completed');
    assert.equal(calls.length, 0, 'standalone leave is idempotent without a write');
  }

  {
    const calls: Call[] = [];
    const store = new FakeStore([
      haState('Bedroom'),
      haState('Kitchen'),
      haState('Office', {state: 'unavailable'}),
    ]);
    const actions = new HomeAssistantSonosActions({
      stateStore: store,
      client: {
        async callService(_domain, service, data) {
          calls.push({service, data});
          store.set([
            haState('Bedroom', {members: ['Bedroom', 'Kitchen']}),
            haState('Kitchen', {members: ['Bedroom', 'Kitchen']}),
            haState('Office', {state: 'unavailable'}),
          ]);
          return {};
        },
      },
    });
    const result = await actions.joinAll(
      'Bedroom', ['Bedroom', 'Kitchen', 'Office']
    ).finished;
    assert.equal(result.status, 'partial');
    assert.deepEqual(result.unavailableRooms, ['Office']);
    assert.deepEqual(calls, [{
      service: 'join',
      data: {
        entity_id: 'media_player.bedroom',
        group_members: ['media_player.kitchen'],
      },
    }], 'join-all makes one application-level join call');
    assert.equal(result.serviceCallCount, 1);
  }

  {
    const calls: Call[] = [];
    let bedroomJoined = false;
    let officeJoined = false;
    const store = new FakeStore([
      haState('Bedroom', {members: ['Bedroom', 'Kitchen']}),
      haState('Kitchen', {members: ['Bedroom', 'Kitchen']}),
      haState('Office'),
    ]);
    const actions = new HomeAssistantSonosActions({
      stateStore: store,
      client: {
        async callService(_domain, service, data) {
          calls.push({service, data});
          if (service === 'unjoin') {
            store.set([
              haState('Bedroom'),
              haState('Kitchen'),
              haState('Office'),
            ]);
          } else {
            const member = (data.group_members as string[])[0];
            bedroomJoined ||= member === SONOS_ROOM_TO_ENTITY.Bedroom;
            officeJoined ||= member === SONOS_ROOM_TO_ENTITY.Office;
            const members: Array<'Kitchen' | 'Bedroom' | 'Office'> = ['Kitchen'];
            if (bedroomJoined) members.push('Bedroom');
            if (officeJoined) members.push('Office');
            store.set([
              bedroomJoined ? haState('Bedroom', {members}) : haState('Bedroom'),
              haState('Kitchen', {members}),
              officeJoined ? haState('Office', {members}) : haState('Office'),
            ]);
          }
          return {};
        },
      },
    });
    const result = await actions.joinAll(
      'Kitchen', ['Kitchen', 'Bedroom', 'Office']
    ).finished;
    assert.equal(result.status, 'completed', result.error);
    assert.equal(result.serviceCallCount, 3);
    assert.deepEqual(calls, [
      {
        service: 'unjoin',
        data: {entity_id: SONOS_ROOM_TO_ENTITY.Kitchen},
      },
      {
        service: 'join',
        data: {
          entity_id: SONOS_ROOM_TO_ENTITY.Kitchen,
          group_members: [SONOS_ROOM_TO_ENTITY.Bedroom],
        },
      },
      {
        service: 'join',
        data: {
          entity_id: SONOS_ROOM_TO_ENTITY.Kitchen,
          group_members: [SONOS_ROOM_TO_ENTITY.Office],
        },
      },
    ], 'join-all detaches a follower, then joins each member to the requested coordinator');
  }

  {
    const calls: Call[] = [];
    let kitchenJoined = false;
    let officeJoined = false;
    const store = new FakeStore([
      haState('Living Room'),
      haState('Bedroom'),
      haState('Kitchen'),
      haState('Office'),
      haState('Guest Bathroom', {state: 'unavailable'}),
    ]);
    const updateObservedGroup = (): void => {
      const members: Array<'Living Room' | 'Kitchen' | 'Office'> = ['Living Room'];
      if (kitchenJoined) members.push('Kitchen');
      if (officeJoined) members.push('Office');
      store.set([
        haState('Living Room', {members}),
        haState('Bedroom'),
        kitchenJoined ? haState('Kitchen', {members}) : haState('Kitchen'),
        officeJoined ? haState('Office', {members}) : haState('Office'),
        haState('Guest Bathroom', {state: 'unavailable'}),
      ]);
    };
    const actions = new HomeAssistantSonosActions({
      stateStore: store,
      client: {
        async callService(_domain, service, data) {
          calls.push({service, data});
          const member = (data.group_members as string[])[0];
          if (member === SONOS_ROOM_TO_ENTITY.Bedroom) {
            throw new HomeAssistantClientError(
              'http',
              'Home Assistant request failed with status 500',
              500
            );
          }
          kitchenJoined ||= member === SONOS_ROOM_TO_ENTITY.Kitchen;
          officeJoined ||= member === SONOS_ROOM_TO_ENTITY.Office;
          updateObservedGroup();
          return {};
        },
      },
    });

    const result = await actions.joinAll('Living Room', [
      'Living Room',
      'Bedroom',
      'Kitchen',
      'Office',
      'Guest Bathroom',
    ]).finished;

    assert.equal(result.status, 'partial');
    assert.deepEqual(result.unavailableRooms, ['Bedroom', 'Guest Bathroom']);
    assert.equal(result.serviceCallCount, 3);
    assert.deepEqual(calls.map(call => call.data.group_members), [
      [SONOS_ROOM_TO_ENTITY.Bedroom],
      [SONOS_ROOM_TO_ENTITY.Kitchen],
      [SONOS_ROOM_TO_ENTITY.Office],
    ], 'a failed room is isolated and later healthy rooms are still submitted');
    assert.deepEqual(
      store.snapshot().entities.get(SONOS_ROOM_TO_ENTITY['Living Room'])
        ?.attributes.group_members,
      [
        SONOS_ROOM_TO_ENTITY['Living Room'],
        SONOS_ROOM_TO_ENTITY.Kitchen,
        SONOS_ROOM_TO_ENTITY.Office,
      ],
      'healthy rooms converge under the requested coordinator despite one stale room'
    );
  }

  {
    const calls: Call[] = [];
    const store = new FakeStore([haState('Kitchen')]);
    const actions = new HomeAssistantSonosActions({
      stateStore: store,
      client: {
        async callService(_domain, service, data) {
          calls.push({service, data});
          return {};
        },
      },
    });
    for (const rooms of [[], ['Kitchen', 'Kitchen']]) {
      assert.throws(
        () => actions.joinAll('Kitchen', rooms as any),
        (error: unknown) => error instanceof SonosBackendError &&
          error.code === 'invalid_request'
      );
    }
    assert.throws(
      () => actions.joinAll('Kitchen', ['Bedroom']),
      (error: unknown) => error instanceof SonosBackendError &&
        error.code === 'invalid_request'
    );
    assert.equal(calls.length, 0, 'invalid join-all input is rejected before HA writes');
  }

  {
    const calls: Call[] = [];
    const store = new FakeStore([
      haState('Bedroom', {
        members: ['Bedroom', 'Kitchen', 'Office'],
        attributes: {volume_level: 0.15},
      }),
      haState('Kitchen', {
        members: ['Bedroom', 'Kitchen', 'Office'],
        attributes: {volume_level: 0.2},
      }),
      haState('Office', {
        members: ['Bedroom', 'Kitchen', 'Office'],
        attributes: {volume_level: 0.3},
      }),
    ]);
    const actions = new HomeAssistantSonosActions({
      stateStore: store,
      client: {
        async callService(_domain, service, data) {
          calls.push({service, data});
          return {};
        },
      },
    });
    await actions.groupVolume('Bedroom', '+5');
    assert.deepEqual(calls.map(call => call.data.volume_level), [0.2, 0.25, 0.35]);
    calls.length = 0;
    await actions.groupVolume('Bedroom', '-5');
    assert.deepEqual(calls.map(call => call.data.volume_level), [0.12, 0.16, 0.24],
      'negative relative volume scales toward the desired group volume');
    calls.length = 0;
    await actions.groupVolume('Bedroom', '10');
    assert.deepEqual(calls.map(call => call.data.volume_level), [0.07, 0.1, 0.14],
      'lower absolute volume scales and rounds each member upward from observed group volume');
    calls.length = 0;
    await actions.groupVolume('Bedroom', '30');
    assert.deepEqual(calls.map(call => call.data.volume_level), [0.23, 0.28, 0.38],
      'higher absolute volume adds the delta from observed group volume');
    calls.length = 0;
    await actions.groupVolume('Bedroom', '0');
    assert.deepEqual(calls.map(call => call.data.volume_level), [0, 0, 0]);
    calls.length = 0;
    await actions.groupVolume('Bedroom', '-50');
    assert.deepEqual(calls.map(call => call.data.volume_level), [0, 0, 0],
      'negative relative volume crossing below one clamps every member to zero');
    calls.length = 0;
    await actions.groupVolume('Bedroom', '+100');
    assert.deepEqual(calls.map(call => call.data.volume_level), [1, 1, 1],
      'positive relative volume clamps every member to one hundred');
  }

  {
    const calls: Call[] = [];
    const store = new FakeStore([
      haState('Bedroom', {members: ['Bedroom', 'Kitchen']}),
      haState('Kitchen', {members: ['Bedroom', 'Kitchen']}),
    ]);
    const actions = new HomeAssistantSonosActions({
      stateStore: store,
      client: {
        async callService(_domain, service, data) {
          calls.push({service, data});
          if (data.entity_id === SONOS_ROOM_TO_ENTITY.Kitchen) {
            throw new Error('Kitchen rejected volume');
          }
          const bedroom = store.current.entities.get(SONOS_ROOM_TO_ENTITY.Bedroom);
          if (bedroom) bedroom.attributes.volume_level = 0.11;
          return {};
        },
      },
    });
    await assert.rejects(
      actions.groupVolume('Bedroom', '+1'),
      (error: unknown) => error instanceof SonosBackendError &&
        error.code === 'volume_partial_failure' &&
        error.message === 'Volume update failed for Kitchen; ' +
          'current observed volumes: Bedroom=11, Kitchen=10'
    );
    assert.equal(calls.length, 2,
      'partial volume failure still attempts each member exactly once');
  }

  {
    const calls: Call[] = [];
    const store = new FakeStore([
      haState('Bedroom', {
        members: ['Bedroom', 'Kitchen', 'Office'],
        attributes: {volume_level: 0.1},
      }),
      haState('Kitchen', {
        members: ['Bedroom', 'Kitchen', 'Office'],
        attributes: {volume_level: 0.1},
      }),
      haState('Office', {
        members: ['Bedroom', 'Kitchen', 'Office'],
        attributes: {volume_level: 0.2},
      }),
    ]);
    const actions = new HomeAssistantSonosActions({
      stateStore: store,
      client: {
        async callService(_domain, service, data) {
          calls.push({service, data});
          return {};
        },
      },
    });
    await actions.normalizeGroupVolume('Bedroom');
    assert.deepEqual(calls, [{
      service: 'volume_set',
      data: {entity_id: SONOS_ROOM_TO_ENTITY.Office, volume_level: 0.1},
    }], '/same writes only members whose observed volume differs from the target');

    calls.length = 0;
    await actions.normalizeGroupVolume('Kitchen');
    assert.deepEqual(calls, [{
      service: 'volume_set',
      data: {entity_id: SONOS_ROOM_TO_ENTITY.Office, volume_level: 0.1},
    }], 'a non-coordinator /same target still skips every already-equal member');

    const office = store.current.entities.get(SONOS_ROOM_TO_ENTITY.Office);
    if (office) office.attributes.volume_level = 0.1;
    calls.length = 0;
    await actions.normalizeGroupVolume('Bedroom');
    assert.equal(calls.length, 0,
      '/same makes no service call when every member already matches');
  }

  {
    const calls: Call[] = [];
    const store = new FakeStore([haState('Bedroom'), haState('Kitchen')]);
    const actions = new HomeAssistantSonosActions({
      stateStore: store,
      client: {
        async callService(_domain, service, data) {
          calls.push({service, data});
          throw new HomeAssistantClientError('timeout', 'HA request timed out');
        },
      },
    });
    const operation = actions.join('Kitchen', 'Bedroom');
    await nextTurn();
    assert.equal(calls.length, 1);
    store.set([
      haState('Bedroom', {members: ['Bedroom', 'Kitchen']}),
      haState('Kitchen', {members: ['Bedroom', 'Kitchen']}),
    ]);
    const observedAfterTimeout = await operation.finished;
    assert.equal(observedAfterTimeout.status, 'completed');
    assert.equal(observedAfterTimeout.serviceCallCount, 1);
    assert.equal(calls.length, 1,
      'a request timeout followed by authoritative success is observed, never resubmitted');
  }

  {
    const calls: Call[] = [];
    const timers: Array<{callback: () => void; cleared: boolean}> = [];
    const store = new FakeStore([haState('Bedroom'), haState('Kitchen')]);
    const actions = new HomeAssistantSonosActions({
      stateStore: store,
      topologyDeadlineMs: 10,
      setTimeout: ((callback: () => void) => {
        const timer = {callback, cleared: false};
        timers.push(timer);
        return timer as any;
      }) as typeof setTimeout,
      clearTimeout: ((timer: any) => {
        timer.cleared = true;
      }) as typeof clearTimeout,
      client: {
        async callService(_domain, service, data) {
          calls.push({service, data});
          return {};
        },
      },
    });
    const operation = actions.join('Kitchen', 'Bedroom');
    await nextTurn();
    assert.equal(calls.length, 1);
    assert.equal(timers.length, 2,
      'the queue deadline and the confirming-observation deadline are both scheduled');
    timers[1].callback();
    const noObservation = await operation.finished;
    assert.equal(noObservation.status, 'timed_out');
    assert.equal(noObservation.serviceCallCount, 1);
    assert.equal(calls.length, 1,
      'a successful service response without confirming state is not resubmitted');
    store.set([
      haState('Bedroom', {members: ['Bedroom', 'Kitchen']}),
      haState('Kitchen', {members: ['Bedroom', 'Kitchen']}),
    ]);
    await nextTurn();
    assert.equal(
      actions.operationQueue.getOperation(operation.operation.id)?.status,
      'timed_out',
      'an observation after the deadline cannot rewrite the terminal result');
    assert.equal(calls.length, 1);
  }

  {
    const calls: Call[] = [];
    const firstJoinGate = deferred<void>();
    const store = new FakeStore([
      haState('Bedroom'),
      haState('Kitchen'),
      haState('Office'),
    ]);
    const actions = new HomeAssistantSonosActions({
      stateStore: store,
      client: {
        async callService(_domain, service, data) {
          calls.push({service, data});
          if (data.entity_id === SONOS_ROOM_TO_ENTITY.Bedroom) {
            await firstJoinGate.promise;
            store.set([
              haState('Bedroom', {members: ['Bedroom', 'Kitchen']}),
              haState('Kitchen', {members: ['Bedroom', 'Kitchen']}),
              haState('Office'),
            ]);
          } else {
            store.set([
              haState('Bedroom'),
              haState('Office', {members: ['Office', 'Kitchen']}),
              haState('Kitchen', {members: ['Office', 'Kitchen']}),
            ]);
          }
          return {};
        },
      },
    });

    const first = actions.joinAll('Bedroom', ['Bedroom', 'Kitchen']);
    await nextTurn();
    const newest = actions.joinAll('Office', ['Office', 'Kitchen']);
    assert.equal(first.operation.serviceCallCount, 1,
      'the accepted operation reports the one Home Assistant call already submitted');
    firstJoinGate.resolve();
    const firstResult = await first.finished;
    const newestResult = await newest.finished;
    assert.equal(firstResult.status, 'superseded');
    assert.equal(firstResult.serviceCallCount, 1);
    assert.equal(newestResult.status, 'completed');
    assert.equal(newestResult.serviceCallCount, 1);
    assert.deepEqual(calls, [
      {
        service: 'join',
        data: {
          entity_id: SONOS_ROOM_TO_ENTITY.Bedroom,
          group_members: [SONOS_ROOM_TO_ENTITY.Kitchen],
        },
      },
      {
        service: 'join',
        data: {
          entity_id: SONOS_ROOM_TO_ENTITY.Office,
          group_members: [SONOS_ROOM_TO_ENTITY.Kitchen],
        },
      },
    ], 'the newest competing join-all executes after the superseded call settles');
    const officeMembers = store.snapshot().entities
      .get(SONOS_ROOM_TO_ENTITY.Office)?.attributes.group_members;
    assert.deepEqual(officeMembers, [
      SONOS_ROOM_TO_ENTITY.Office,
      SONOS_ROOM_TO_ENTITY.Kitchen,
    ], 'the newest join-all owns the final authoritative topology');
  }

  {
    const calls: Call[] = [];
    const store = new FakeStore([
      haState('Bedroom'),
      haState('Kitchen'),
      haState('Office'),
    ]);
    const actions = new HomeAssistantSonosActions({
      stateStore: store,
      client: {
        async callService(_domain, service, data) {
          calls.push({service, data});
          if (data.entity_id === SONOS_ROOM_TO_ENTITY.Office) {
            store.set([
              haState('Bedroom'),
              haState('Office', {members: ['Office', 'Kitchen']}),
              haState('Kitchen', {members: ['Office', 'Kitchen']}),
            ]);
          }
          return {};
        },
      },
    });

    const waiting = actions.joinAll('Bedroom', ['Bedroom', 'Kitchen']);
    await nextTurn();
    assert.equal(calls.length, 1, 'first join-all is awaiting authoritative observation');
    const newest = actions.joinAll('Office', ['Office', 'Kitchen']);
    await nextTurn();
    await nextTurn();
    assert.equal(calls.length, 2,
      'supersession cancels the old observation wait and starts the newest operation promptly');
    assert.equal((await waiting.finished).status, 'superseded');
    assert.equal((await newest.finished).status, 'completed');
    assert.deepEqual(calls.map(call => call.data.entity_id), [
      SONOS_ROOM_TO_ENTITY.Bedroom,
      SONOS_ROOM_TO_ENTITY.Office,
    ]);
  }

  {
    const calls: Call[] = [];
    const joinGate = deferred<void>();
    const store = new FakeStore([haState('Bedroom'), haState('Kitchen')]);
    const actions = new HomeAssistantSonosActions({
      stateStore: store,
      client: {
        async callService(_domain, service, data) {
          calls.push({service, data});
          if (service === 'join') {
            await joinGate.promise;
          } else if (service === 'unjoin') {
            store.set([haState('Bedroom'), haState('Kitchen')]);
          }
          return {};
        },
      },
    });
    const joinAll = actions.joinAll('Bedroom', ['Bedroom', 'Kitchen']);
    await nextTurn();
    const leave = actions.leave('Kitchen');
    store.set([
      haState('Bedroom', {members: ['Bedroom', 'Kitchen']}),
      haState('Kitchen', {members: ['Bedroom', 'Kitchen']}),
    ]);
    joinGate.resolve();
    assert.equal((await joinAll.finished).status, 'superseded');
    assert.equal((await leave.finished).status, 'completed');
    assert.deepEqual(calls.map(call => call.service), ['join', 'unjoin'],
      'the newer manual mutation runs once after the in-flight join settles');
  }

  {
    const calls: Call[] = [];
    const store = new FakeStore([haState('Kitchen')]);
    const actions = new HomeAssistantSonosActions({
      stateStore: store,
      client: {
        async callService(_domain, service, data) {
          calls.push({service, data});
          return {};
        },
      },
    });
    assert.throws(
      () => actions.join('Not a room' as any, 'Kitchen'),
      /Unknown Sonos room/
    );
    assert.equal(calls.length, 0);
    assert.equal(SONOS_ROOM_TO_ENTITY.Kitchen, 'media_player.kitchen');
  }
};

run().catch(error => {
  console.error(error);
  process.exit(1);
});
