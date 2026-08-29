import {strict as assert} from 'assert';

import {
  HomeAssistantStateEventHandlers,
  HomeAssistantStateSubscription,
} from './home-assistant-client';
import {HomeAssistantStateStore} from './home-assistant-state-store';
import {deferred, haState, nextTurn} from './home-assistant-test-fixtures';

const run = async (): Promise<void> => {
  let now = 0;
  const timers: Array<{callback: () => void; cleared: boolean}> = [];
  const handlers: HomeAssistantStateEventHandlers[] = [];
  const snapshots = [
    deferred<ReturnType<typeof haState>[]>(),
    deferred<ReturnType<typeof haState>[]>(),
  ];
  let snapshotCall = 0;
  let closeCount = 0;
  const client = {
    async getStates() {
      return snapshots[snapshotCall++].promise;
    },
    async connectStateEvents(nextHandlers: HomeAssistantStateEventHandlers) {
      handlers.push(nextHandlers);
      return {
        close: () => { closeCount += 1; },
      } satisfies HomeAssistantStateSubscription;
    },
  };
  const store = new HomeAssistantStateStore({
    client,
    entityIds: ['media_player.kitchen', 'media_player.bathroom'],
    now: () => now,
    staleAfterMs: 30_000,
    reconnectInitialMs: 10,
    reconnectMaxMs: 20,
    setTimeout: ((callback: () => void) => {
      const timer = {callback, cleared: false};
      timers.push(timer);
      return timer as any;
    }) as typeof setTimeout,
    clearTimeout: ((timer: any) => {
      timer.cleared = true;
    }) as typeof clearTimeout,
  });

  const starting = store.start();
  await nextTurn();
  const newer = haState('Kitchen', {
    updated: '2026-08-28T12:00:02.000Z',
    attributes: {volume_level: 0.8},
  });
  handlers[0].onStateChanged({
    entityId: newer.entity_id,
    oldState: null,
    newState: newer,
  });
  handlers[0].onStateChanged({
    entityId: newer.entity_id,
    oldState: null,
    newState: newer,
  });
  handlers[0].onStateChanged({
    entityId: 'media_player.bathroom',
    oldState: haState('Bathroom'),
    newState: null,
  });
  handlers[0].onStateChanged({
    entityId: 'media_player.bathroom',
    oldState: haState('Bathroom'),
    newState: null,
  });
  snapshots[0].resolve([haState('Kitchen', {
    updated: '2026-08-28T12:00:01.000Z',
    attributes: {volume_level: 0.1},
  }), haState('Bathroom')]);
  await starting;
  assert.equal(store.snapshot().freshness, 'live');
  assert.equal(store.getEntity('media_player.kitchen')?.attributes.volume_level, 0.8,
    'duplicate state events are idempotent and a delayed snapshot cannot overwrite them');
  assert.equal(store.getEntity('media_player.bathroom'), undefined,
    'duplicate deletion events are idempotent and block delayed snapshot resurrection');

  handlers[0].onStateChanged({
    entityId: newer.entity_id,
    oldState: newer,
    newState: haState('Kitchen', {
      updated: '2026-08-28T12:00:01.500Z',
      attributes: {volume_level: 0.2},
    }),
  });
  assert.equal(store.getEntity('media_player.kitchen')?.attributes.volume_level, 0.8,
    'out-of-order events must be ignored');

  now = 1_000;
  handlers[0].onDisconnect();
  assert.equal(store.snapshot().freshness, 'stale');
  assert.throws(
    () => store.assertCommandable(['media_player.kitchen']),
    /not fresh enough/,
    'commands fail closed at the exact disconnect instant'
  );
  now = 30_999;
  assert.equal(store.snapshot().freshness, 'stale');
  now = 31_000;
  assert.equal(store.snapshot().freshness, 'unknown', '30,000ms is the unknown boundary');
  assert.throws(
    () => store.assertCommandable(['media_player.kitchen']),
    /not fresh enough/
  );

  now = 31_010;
  timers[0].callback();
  await nextTurn();
  snapshots[1].resolve([haState('Kitchen', {
    updated: '2026-08-28T12:00:03.000Z',
    attributes: {volume_level: 0.3},
  })]);
  await nextTurn();
  assert.equal(handlers.length, 2);
  assert.equal(store.snapshot().freshness, 'live');
  assert.equal(store.getEntity('media_player.kitchen')?.attributes.volume_level, 0.3);

  store.stop();
  assert.equal(closeCount, 1);
  assert.equal(store.snapshot().freshness, 'unknown');

  {
    const reconnectTimers: Array<{callback: () => void; delay: number}> = [];
    const interruptedSnapshot = deferred<ReturnType<typeof haState>[]>();
    const reconnectSnapshots: Array<Promise<ReturnType<typeof haState>[]>> = [
      Promise.resolve([haState('Kitchen', {
        updated: '2026-08-28T12:00:01.000Z',
        attributes: {volume_level: 0.1},
      })]),
      interruptedSnapshot.promise,
      Promise.resolve([haState('Kitchen', {
        updated: '2026-08-28T12:00:03.000Z',
        attributes: {volume_level: 0.3},
      })]),
    ];
    const reconnectHandlers: HomeAssistantStateEventHandlers[] = [];
    const subscriptionCloseCounts: number[] = [];
    let snapshotIndex = 0;
    const disconnectingResnapshotStore = new HomeAssistantStateStore({
      entityIds: ['media_player.kitchen'],
      reconnectInitialMs: 10,
      reconnectMaxMs: 20,
      client: {
        async connectStateEvents(nextHandlers) {
          const subscriptionIndex = reconnectHandlers.length;
          reconnectHandlers.push(nextHandlers);
          subscriptionCloseCounts[subscriptionIndex] = 0;
          let closed = false;
          return {
            close() {
              if (!closed) {
                closed = true;
                subscriptionCloseCounts[subscriptionIndex] += 1;
              }
            },
          };
        },
        async getStates() {
          return reconnectSnapshots[snapshotIndex++];
        },
      },
      setTimeout: ((callback: () => void, delay = 0) => {
        const timer = {callback, delay};
        reconnectTimers.push(timer);
        return timer as any;
      }) as typeof setTimeout,
      clearTimeout: (() => undefined) as typeof clearTimeout,
    });

    await disconnectingResnapshotStore.start();
    assert.equal(disconnectingResnapshotStore.snapshot().freshness, 'live');
    reconnectHandlers[0].onDisconnect();
    assert.equal(disconnectingResnapshotStore.snapshot().freshness, 'stale');
    assert.equal(reconnectTimers.length, 1);

    reconnectTimers[0].callback();
    await nextTurn();
    assert.equal(reconnectHandlers.length, 2);
    assert.equal(disconnectingResnapshotStore.snapshot().freshness, 'stale',
      'opening a replacement socket does not make state live before its snapshot');

    reconnectHandlers[1].onStateChanged({
      entityId: 'media_player.kitchen',
      oldState: haState('Kitchen'),
      newState: haState('Kitchen', {
        updated: '2026-08-28T12:00:02.000Z',
        attributes: {volume_level: 0.2},
      }),
    });
    reconnectHandlers[1].onDisconnect(new Error('replacement socket closed'));
    assert.equal(reconnectTimers.length, 2,
      'disconnect during replacement resnapshot schedules exactly one further reconnect');

    interruptedSnapshot.resolve([haState('Kitchen', {
      updated: '2026-08-28T12:00:04.000Z',
      attributes: {volume_level: 0.9},
    })]);
    await nextTurn();
    await nextTurn();
    assert.equal(subscriptionCloseCounts[1], 1,
      'the abandoned replacement subscription is closed exactly once');
    assert.equal(disconnectingResnapshotStore.snapshot().freshness, 'stale');
    assert.equal(
      disconnectingResnapshotStore.getEntity('media_player.kitchen')?.attributes.volume_level,
      0.2,
      'the abandoned replacement snapshot cannot write after its disconnect'
    );
    assert.equal(reconnectTimers.length, 2,
      'completion of the abandoned snapshot does not schedule a duplicate reconnect');

    reconnectTimers[1].callback();
    await nextTurn();
    await nextTurn();
    assert.equal(disconnectingResnapshotStore.snapshot().freshness, 'live');
    assert.equal(
      disconnectingResnapshotStore.getEntity('media_player.kitchen')?.attributes.volume_level,
      0.3,
      'only the next authenticated replacement snapshot restores live state'
    );
    assert.equal(reconnectHandlers.length, 3);
    disconnectingResnapshotStore.stop();
    assert.equal(subscriptionCloseCounts[2], 1,
      'shutdown closes the sole current replacement subscription');
  }

  {
    const reconnectTimers: Array<() => void> = [];
    let stateAttempts = 0;
    let activeSubscriptions = 0;
    let failedSnapshotCloseCount = 0;
    const recoveringStore = new HomeAssistantStateStore({
      entityIds: ['media_player.kitchen'],
      reconnectInitialMs: 10,
      client: {
        async connectStateEvents() {
          activeSubscriptions += 1;
          let closed = false;
          return {
            close() {
              if (!closed) {
                closed = true;
                activeSubscriptions -= 1;
                failedSnapshotCloseCount += 1;
              }
            },
          };
        },
        async getStates() {
          stateAttempts += 1;
          if (stateAttempts === 1) {
            throw new Error('snapshot failed');
          }
          return [haState('Kitchen')];
        },
      },
      setTimeout: ((callback: () => void) => {
        reconnectTimers.push(callback);
        return callback as any;
      }) as typeof setTimeout,
      clearTimeout: (() => undefined) as typeof clearTimeout,
    });

    await recoveringStore.start();
    assert.equal(activeSubscriptions, 0,
      'a failed initial snapshot closes its authenticated subscription');
    assert.equal(failedSnapshotCloseCount, 1);
    assert.equal(reconnectTimers.length, 1);

    reconnectTimers[0]();
    await nextTurn();
    await nextTurn();
    assert.equal(recoveringStore.snapshot().freshness, 'live');
    assert.equal(activeSubscriptions, 1,
      'recovery leaves exactly one current subscription');
    recoveringStore.stop();
    assert.equal(activeSubscriptions, 0);
    assert.equal(failedSnapshotCloseCount, 2,
      'each created subscription is closed exactly once');
  }

  {
    const reconnectTimers: Array<{callback: () => void; delay: number}> = [];
    const successfulHandlers: HomeAssistantStateEventHandlers[] = [];
    let allowSuccess = false;
    const backoffStore = new HomeAssistantStateStore({
      entityIds: ['media_player.kitchen'],
      client: {
        async connectStateEvents(nextHandlers) {
          if (!allowSuccess) {
            throw new Error('offline');
          }
          successfulHandlers.push(nextHandlers);
          return {close() {}};
        },
        async getStates() {
          return [haState('Kitchen')];
        },
      },
      setTimeout: ((callback: () => void, delay = 0) => {
        const timer = {callback, delay};
        reconnectTimers.push(timer);
        return timer as any;
      }) as typeof setTimeout,
      clearTimeout: (() => undefined) as typeof clearTimeout,
    });

    await backoffStore.start();
    for (let index = 0; index < 6; index += 1) {
      reconnectTimers[index].callback();
      await nextTurn();
      await nextTurn();
    }
    assert.deepEqual(
      reconnectTimers.map(timer => timer.delay),
      [500, 1_000, 2_000, 4_000, 8_000, 10_000, 10_000],
      'reconnect backoff doubles to the frozen ten-second cap'
    );

    allowSuccess = true;
    reconnectTimers[6].callback();
    await nextTurn();
    await nextTurn();
    assert.equal(backoffStore.snapshot().freshness, 'live');
    assert.equal(successfulHandlers.length, 1);

    successfulHandlers[0].onDisconnect();
    assert.equal(reconnectTimers.at(-1)?.delay, 500,
      'an authenticated resnapshot resets reconnect backoff to 500ms');
    backoffStore.stop();
  }

  {
    let websocketAbortCount = 0;
    let snapshotCalls = 0;
    const reconnectCallbacks: Array<() => void> = [];
    const startingStore = new HomeAssistantStateStore({
      entityIds: ['media_player.kitchen'],
      client: {
        connectStateEvents(_handlers, signal) {
          return new Promise<HomeAssistantStateSubscription>((_resolve, reject) => {
            signal?.addEventListener('abort', () => {
              websocketAbortCount += 1;
              reject(new Error('cancelled'));
            }, {once: true});
          });
        },
        async getStates() {
          snapshotCalls += 1;
          return [];
        },
      },
      setTimeout: ((callback: () => void) => {
        reconnectCallbacks.push(callback);
        return callback as any;
      }) as typeof setTimeout,
      clearTimeout: (() => undefined) as typeof clearTimeout,
    });

    const starting = startingStore.start();
    await nextTurn();
    startingStore.stop();
    await starting;
    assert.equal(websocketAbortCount, 1,
      'stop aborts an in-flight WebSocket authentication/subscription');
    assert.equal(snapshotCalls, 0);
    assert.equal(reconnectCallbacks.length, 0,
      'startup cancellation must not schedule reconnect');
    assert.equal(startingStore.snapshot().freshness, 'unknown');
  }

  {
    let snapshotAbortCount = 0;
    let subscriptionCloseCount = 0;
    let snapshotStarted = false;
    const reconnectCallbacks: Array<() => void> = [];
    const snapshotStore = new HomeAssistantStateStore({
      entityIds: ['media_player.kitchen'],
      client: {
        async connectStateEvents(_handlers, signal) {
          let closed = false;
          const close = () => {
            if (!closed) {
              closed = true;
              subscriptionCloseCount += 1;
            }
          };
          signal?.addEventListener('abort', close, {once: true});
          return {close};
        },
        getStates(signal) {
          snapshotStarted = true;
          return new Promise<ReturnType<typeof haState>[]>((_resolve, reject) => {
            signal?.addEventListener('abort', () => {
              snapshotAbortCount += 1;
              reject(new Error('cancelled'));
            }, {once: true});
          });
        },
      },
      setTimeout: ((callback: () => void) => {
        reconnectCallbacks.push(callback);
        return callback as any;
      }) as typeof setTimeout,
      clearTimeout: (() => undefined) as typeof clearTimeout,
    });

    const starting = snapshotStore.start();
    await nextTurn();
    assert.equal(snapshotStarted, true);
    snapshotStore.stop();
    await starting;
    assert.equal(snapshotAbortCount, 1, 'stop aborts the in-flight REST snapshot');
    assert.equal(subscriptionCloseCount, 1,
      'the authenticated subscription closes exactly once during snapshot cancellation');
    assert.equal(reconnectCallbacks.length, 0,
      'snapshot cancellation must not schedule reconnect');
    assert.equal(snapshotStore.snapshot().freshness, 'unknown');
  }

  {
    let connectAttempts = 0;
    const reconnectTimers: Array<{callback: () => void; cleared: boolean}> = [];
    const reconnectStore = new HomeAssistantStateStore({
      entityIds: ['media_player.kitchen'],
      client: {
        async connectStateEvents() {
          connectAttempts += 1;
          throw new Error('offline');
        },
        async getStates() {
          return [];
        },
      },
      setTimeout: ((callback: () => void) => {
        const timer = {callback, cleared: false};
        reconnectTimers.push(timer);
        return timer as any;
      }) as typeof setTimeout,
      clearTimeout: ((timer: any) => {
        timer.cleared = true;
      }) as typeof clearTimeout,
    });

    await reconnectStore.start();
    assert.equal(connectAttempts, 1);
    assert.equal(reconnectTimers.length, 1);
    reconnectStore.stop();
    assert.equal(reconnectTimers[0].cleared, true);
    reconnectTimers[0].callback();
    await nextTurn();
    assert.equal(connectAttempts, 1, 'a stopped store never begins a queued reconnect');
  }
};

run().catch(error => {
  console.error(error);
  process.exit(1);
});
