import {strict as assert} from 'assert';

import {
  HomeAssistantClient,
  HomeAssistantClientError,
  WebSocketLike,
} from './home-assistant-client';
import {haState} from './home-assistant-test-fixtures';

class FakeSocket implements WebSocketLike {
  readonly readyState = 1;
  readonly sent: string[] = [];
  readonly listeners = new Map<string, Set<(event: any) => void>>();
  closeCount = 0;

  send(data: string): void {
    this.sent.push(data);
  }

  close(): void {
    this.closeCount += 1;
  }

  addEventListener(type: string, listener: (event: any) => void): void {
    const listeners = this.listeners.get(type) || new Set();
    listeners.add(listener);
    this.listeners.set(type, listeners);
  }

  removeEventListener(type: string, listener: (event: any) => void): void {
    this.listeners.get(type)?.delete(listener);
  }

  emit(type: string, event: any = {}): void {
    for (const listener of this.listeners.get(type) || []) {
      listener(event);
    }
  }

  message(value: unknown): void {
    this.emit('message', {data: JSON.stringify(value)});
  }

  rawMessage(value: string): void {
    this.emit('message', {data: value});
  }
}

interface FakeTimer {
  id: number;
  at: number;
  callback: () => void;
}

class FakeClock {
  now = 0;
  private nextId = 1;
  private readonly timers = new Map<number, FakeTimer>();

  readonly setTimeout = ((callback: () => void, delay = 0): any => {
    const id = this.nextId++;
    this.timers.set(id, {id, at: this.now + delay, callback});
    return id;
  }) as typeof setTimeout;

  readonly clearTimeout = ((timer: any): void => {
    this.timers.delete(Number(timer));
  }) as typeof clearTimeout;

  advanceTo(target: number): void {
    assert.ok(target >= this.now, 'fake time cannot move backwards');
    while (true) {
      const next = [...this.timers.values()]
        .filter(timer => timer.at <= target)
        .sort((left, right) => left.at - right.at || left.id - right.id)[0];
      if (!next) {
        break;
      }
      this.timers.delete(next.id);
      this.now = next.at;
      next.callback();
    }
    this.now = target;
  }

  get pendingCount(): number {
    return this.timers.size;
  }
}

const stateEvent = (
  entityId = 'media_player.kitchen',
  subscriptionId = 1
): Record<string, unknown> => ({
  id: subscriptionId,
  type: 'event',
  event: {
    time_fired: '2026-08-28T12:00:01.000Z',
    data: {
      entity_id: entityId,
      old_state: null,
      new_state: haState('Kitchen'),
    },
  },
});

const finishSubscription = async (
  socket: FakeSocket,
  connected: ReturnType<HomeAssistantClient['connectStateEvents']>
) => {
  socket.message({type: 'auth_required'});
  socket.message({type: 'auth_ok'});
  socket.message({id: 1, type: 'result', success: true});
  return connected;
};

const flushMicrotasks = async (): Promise<void> => {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
};

const run = async (): Promise<void> => {
  {
    const requests: Array<{url: string; init?: RequestInit}> = [];
    const client = new HomeAssistantClient({
      token: 'recognizable-secret',
      fetch: (async (url: string | URL | Request, init?: RequestInit) => {
        requests.push({url: String(url), init});
        return new Response(JSON.stringify([haState('Kitchen')]), {
          status: 200,
          headers: {'content-type': 'application/json'},
        });
      }) as typeof fetch,
    });
    const states = await client.getStates();
    assert.equal(states[0].entity_id, 'media_player.kitchen');
    assert.equal(requests[0].url, 'http://supervisor/core/api/states');
    assert.equal((requests[0].init?.headers as Record<string, string>).Authorization,
      'Bearer recognizable-secret');
    assert.equal(requests[0].init?.redirect, 'error');
  }

  {
    const client = new HomeAssistantClient({
      token: 'recognizable-secret',
      fetch: (async () => new Response('denied recognizable-secret', {status: 401})) as typeof fetch,
    });
    await assert.rejects(
      client.getStates(),
      (error: unknown) => error instanceof HomeAssistantClientError &&
        error.code === 'authentication' &&
        !error.message.includes('recognizable-secret')
    );
  }

  {
    const clock = new FakeClock();
    const client = new HomeAssistantClient({
      token: 'headers-timeout-secret',
      setTimeout: clock.setTimeout,
      clearTimeout: clock.clearTimeout,
      fetch: ((_url: string | URL | Request, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => {
            reject(new DOMException('aborted', 'AbortError'));
          });
        })) as typeof fetch,
    });

    let settled = false;
    const states = client.getStates();
    void states.then(
      () => { settled = true; },
      () => { settled = true; }
    );
    clock.advanceTo(9_999);
    await flushMicrotasks();
    assert.equal(settled, false);
    clock.advanceTo(10_000);
    await assert.rejects(states, (error: unknown) =>
      error instanceof HomeAssistantClientError && error.code === 'timeout');
    assert.equal(clock.pendingCount, 0);
  }

  {
    const clock = new FakeClock();
    let fetchReturnedHeaders = false;
    const client = new HomeAssistantClient({
      token: 'json-timeout-secret',
      setTimeout: clock.setTimeout,
      clearTimeout: clock.clearTimeout,
      fetch: (async () => {
        fetchReturnedHeaders = true;
        return new Response(new ReadableStream<Uint8Array>({
          start: controller => {
            controller.enqueue(new TextEncoder().encode('[{"entity_id":'));
          },
        }), {
          status: 200,
          headers: {'content-type': 'application/json'},
        });
      }) as typeof fetch,
    });

    let settled = false;
    const states = client.getStates();
    void states.then(
      () => { settled = true; },
      () => { settled = true; }
    );
    await flushMicrotasks();
    assert.equal(fetchReturnedHeaders, true);
    clock.advanceTo(9_999);
    await flushMicrotasks();
    assert.equal(settled, false, 'headers alone must not complete a JSON request');
    clock.advanceTo(10_000);
    await assert.rejects(states, (error: unknown) =>
      error instanceof HomeAssistantClientError &&
      error.code === 'timeout' &&
      /response completed/.test(error.message));
    assert.equal(clock.pendingCount, 0);
  }

  {
    const clock = new FakeClock();
    const client = new HomeAssistantClient({
      token: 'binary-timeout-secret',
      setTimeout: clock.setTimeout,
      clearTimeout: clock.clearTimeout,
      fetch: (async () => new Response(new ReadableStream<Uint8Array>({
        start: controller => {
          controller.enqueue(new Uint8Array([0xff, 0xd8, 0xff]));
        },
      }), {
        status: 200,
        headers: {'content-type': 'image/jpeg'},
      })) as typeof fetch,
    });

    const response = await client.fetchAuthenticatedPath('/api/media_proxy/test');
    let settled = false;
    const bytes = response.arrayBuffer();
    void bytes.then(
      () => { settled = true; },
      () => { settled = true; }
    );
    await flushMicrotasks();
    clock.advanceTo(9_999);
    await flushMicrotasks();
    assert.equal(settled, false, 'headers alone must not complete an artwork request');
    clock.advanceTo(10_000);
    await assert.rejects(bytes, (error: unknown) =>
      error instanceof HomeAssistantClientError &&
      error.code === 'timeout' &&
      /response completed/.test(error.message));
    assert.equal(clock.pendingCount, 0);
  }

  {
    const clock = new FakeClock();
    const client = new HomeAssistantClient({
      token: 'completed-body-secret',
      setTimeout: clock.setTimeout,
      clearTimeout: clock.clearTimeout,
      fetch: (async () => new Response(JSON.stringify([haState('Kitchen')]), {
        status: 200,
        headers: {'content-type': 'application/json'},
      })) as typeof fetch,
    });
    assert.equal((await client.getStates())[0].entity_id, 'media_player.kitchen');
    assert.equal(clock.pendingCount, 0, 'complete bodies must release their request timer');
    clock.advanceTo(10_000);
  }

  {
    const clock = new FakeClock();
    const cancellation = new AbortController();
    let fetchAbortCount = 0;
    let bodyCancelCount = 0;
    let fetchReturnedHeaders = false;
    const client = new HomeAssistantClient({
      token: 'snapshot-cancellation-secret',
      setTimeout: clock.setTimeout,
      clearTimeout: clock.clearTimeout,
      fetch: (async (_url: string | URL | Request, init?: RequestInit) => {
        init?.signal?.addEventListener('abort', () => {
          fetchAbortCount += 1;
        });
        fetchReturnedHeaders = true;
        return new Response(new ReadableStream<Uint8Array>({
          start: controller => {
            controller.enqueue(new TextEncoder().encode('[{"entity_id":'));
          },
          cancel: () => {
            bodyCancelCount += 1;
          },
        }), {
          status: 200,
          headers: {'content-type': 'application/json'},
        });
      }) as typeof fetch,
    });

    const states = client.getStates(cancellation.signal);
    await flushMicrotasks();
    assert.equal(fetchReturnedHeaders, true);
    cancellation.abort();
    await assert.rejects(states, (error: unknown) =>
      error instanceof HomeAssistantClientError && error.code === 'cancelled');
    assert.equal(fetchAbortCount, 1, 'snapshot cancellation must abort fetch transport');
    assert.equal(bodyCancelCount, 1, 'snapshot cancellation must cancel the open body');
    assert.equal(clock.pendingCount, 0);
  }

  {
    const socket = new FakeSocket();
    const clock = new FakeClock();
    const cancellation = new AbortController();
    let disconnects = 0;
    const client = new HomeAssistantClient({
      token: 'startup-cancellation-secret',
      webSocketFactory: () => socket,
      setTimeout: clock.setTimeout,
      clearTimeout: clock.clearTimeout,
    });
    const connected = client.connectStateEvents({
      onStateChanged: () => undefined,
      onDisconnect: () => { disconnects += 1; },
    }, cancellation.signal);

    cancellation.abort();
    await assert.rejects(connected, (error: unknown) =>
      error instanceof HomeAssistantClientError && error.code === 'cancelled');
    assert.equal(socket.closeCount, 1);
    assert.equal(clock.pendingCount, 0);
    socket.emit('close');
    assert.equal(disconnects, 0, 'intentional startup cancellation is not a disconnect');
  }

  {
    const socket = new FakeSocket();
    const clock = new FakeClock();
    const cancellation = new AbortController();
    let disconnects = 0;
    const client = new HomeAssistantClient({
      token: 'subscription-cancellation-secret',
      webSocketFactory: () => socket,
      setTimeout: clock.setTimeout,
      clearTimeout: clock.clearTimeout,
    });
    const connected = client.connectStateEvents({
      onStateChanged: () => undefined,
      onDisconnect: () => { disconnects += 1; },
    }, cancellation.signal);
    await finishSubscription(socket, connected);
    assert.equal(clock.pendingCount, 2);

    cancellation.abort();
    assert.equal(socket.closeCount, 1);
    assert.equal(clock.pendingCount, 0);
    socket.emit('close');
    assert.equal(disconnects, 0, 'intentional subscription cancellation is not a disconnect');
  }

  {
    const socket = new FakeSocket();
    const changed: string[] = [];
    let disconnects = 0;
    const client = new HomeAssistantClient({
      token: 'ws-secret',
      webSocketFactory: () => socket,
    });
    const connected = client.connectStateEvents({
      onStateChanged: event => changed.push(event.entityId),
      onDisconnect: () => { disconnects += 1; },
    });
    socket.message({type: 'auth_required'});
    assert.deepEqual(JSON.parse(socket.sent[0]), {type: 'auth', access_token: 'ws-secret'});
    socket.message({type: 'auth_ok'});
    assert.deepEqual(JSON.parse(socket.sent[1]), {
      id: 1,
      type: 'subscribe_events',
      event_type: 'state_changed',
    });
    socket.message({id: 1, type: 'result', success: true});
    const subscription = await connected;
    socket.message(stateEvent());
    assert.deepEqual(changed, ['media_player.kitchen']);
    subscription.close();
    socket.emit('close');
    assert.equal(disconnects, 0);
  }

  {
    const socket = new FakeSocket();
    const clock = new FakeClock();
    const disconnects: Array<Error | undefined> = [];
    const client = new HomeAssistantClient({
      token: 'heartbeat-secret',
      webSocketFactory: () => socket,
      setTimeout: clock.setTimeout,
      clearTimeout: clock.clearTimeout,
    });
    const connected = client.connectStateEvents({
      onStateChanged: () => undefined,
      onDisconnect: error => disconnects.push(error),
    });
    await finishSubscription(socket, connected);

    clock.advanceTo(14_999);
    assert.equal(socket.sent.filter(item => JSON.parse(item).type === 'ping').length, 0);
    clock.advanceTo(15_000);
    assert.deepEqual(JSON.parse(socket.sent[socket.sent.length - 1]), {id: 2, type: 'ping'});
    clock.advanceTo(44_999);
    assert.equal(disconnects.length, 0);
    assert.equal(socket.closeCount, 0);
    clock.advanceTo(45_000);
    assert.equal(disconnects.length, 1);
    assert.ok(disconnects[0] instanceof HomeAssistantClientError);
    assert.equal((disconnects[0] as HomeAssistantClientError).code, 'timeout');
    assert.match(disconnects[0]?.message || '', /liveness timed out/);
    assert.equal(socket.closeCount, 1);
    clock.advanceTo(90_000);
    assert.equal(disconnects.length, 1);
  }

  {
    const socket = new FakeSocket();
    const clock = new FakeClock();
    const disconnects: Array<Error | undefined> = [];
    const client = new HomeAssistantClient({
      token: 'socket-error-secret',
      webSocketFactory: () => socket,
      setTimeout: clock.setTimeout,
      clearTimeout: clock.clearTimeout,
    });
    const connected = client.connectStateEvents({
      onStateChanged: () => undefined,
      onDisconnect: error => disconnects.push(error),
    });
    await finishSubscription(socket, connected);
    assert.ok(clock.pendingCount > 0);

    socket.emit('error');
    assert.equal(disconnects.length, 1);
    assert.ok(disconnects[0] instanceof HomeAssistantClientError);
    assert.equal((disconnects[0] as HomeAssistantClientError).code, 'network');
    assert.equal(socket.closeCount, 1, 'a subscribed socket error closes the transport');
    assert.equal(clock.pendingCount, 0, 'a subscribed socket error clears all timers');
    socket.emit('close');
    assert.equal(disconnects.length, 1, 'socket error notifies disconnect exactly once');
  }

  {
    const socket = new FakeSocket();
    const clock = new FakeClock();
    const changed: string[] = [];
    let disconnects = 0;
    const client = new HomeAssistantClient({
      token: 'event-liveness-secret',
      webSocketFactory: () => socket,
      setTimeout: clock.setTimeout,
      clearTimeout: clock.clearTimeout,
    });
    const connected = client.connectStateEvents({
      onStateChanged: event => changed.push(event.entityId),
      onDisconnect: () => { disconnects += 1; },
    });
    await finishSubscription(socket, connected);

    clock.advanceTo(30_000);
    socket.message(stateEvent());
    assert.deepEqual(changed, ['media_player.kitchen']);
    clock.advanceTo(45_000);
    assert.equal(disconnects, 0, 'accepted subscription traffic must reset liveness');
    assert.deepEqual(JSON.parse(socket.sent[socket.sent.length - 1]), {id: 3, type: 'ping'});
    clock.advanceTo(74_999);
    assert.equal(disconnects, 0);
    clock.advanceTo(75_000);
    assert.equal(disconnects, 1);
  }

  {
    const socket = new FakeSocket();
    const clock = new FakeClock();
    let disconnects = 0;
    const client = new HomeAssistantClient({
      token: 'pong-liveness-secret',
      webSocketFactory: () => socket,
      setTimeout: clock.setTimeout,
      clearTimeout: clock.clearTimeout,
    });
    const connected = client.connectStateEvents({
      onStateChanged: () => undefined,
      onDisconnect: () => { disconnects += 1; },
    });
    await finishSubscription(socket, connected);

    clock.advanceTo(15_000);
    assert.deepEqual(JSON.parse(socket.sent[socket.sent.length - 1]), {id: 2, type: 'ping'});
    clock.advanceTo(20_000);
    socket.message({id: 2, type: 'pong'});
    clock.advanceTo(34_999);
    assert.equal(socket.sent.filter(item => JSON.parse(item).type === 'ping').length, 1);
    clock.advanceTo(35_000);
    assert.deepEqual(JSON.parse(socket.sent[socket.sent.length - 1]), {id: 3, type: 'ping'});
    clock.advanceTo(64_999);
    assert.equal(disconnects, 0);
    clock.advanceTo(65_000);
    assert.equal(disconnects, 1, 'matching pong must move the 45-second deadline');
  }

  {
    const socket = new FakeSocket();
    const clock = new FakeClock();
    const protocolErrors: string[] = [];
    let disconnects = 0;
    const client = new HomeAssistantClient({
      token: 'ignored-traffic-secret',
      webSocketFactory: () => socket,
      setTimeout: clock.setTimeout,
      clearTimeout: clock.clearTimeout,
    });
    const connected = client.connectStateEvents({
      onStateChanged: () => undefined,
      onDisconnect: () => { disconnects += 1; },
      onProtocolError: error => protocolErrors.push(error.message),
    });
    await finishSubscription(socket, connected);

    clock.advanceTo(20_000);
    socket.message({id: 999, type: 'pong'});
    clock.advanceTo(25_000);
    socket.rawMessage('{not-json');
    clock.advanceTo(30_000);
    socket.message({id: 1, type: 'event', event: {data: {}}});
    clock.advanceTo(40_000);
    socket.message(stateEvent('media_player.kitchen', 999));
    assert.equal(protocolErrors.length, 2);
    clock.advanceTo(44_999);
    assert.equal(disconnects, 0);
    clock.advanceTo(45_000);
    assert.equal(disconnects, 1,
      'wrong-id, malformed, and unrelated frames must not reset liveness');
  }

  {
    const sockets = [new FakeSocket(), new FakeSocket(), new FakeSocket()];
    const clock = new FakeClock();
    let socketIndex = 0;
    const changed: string[] = [];
    const client = new HomeAssistantClient({
      token: 'reconnect-secret',
      webSocketFactory: () => sockets[socketIndex++],
      setTimeout: clock.setTimeout,
      clearTimeout: clock.clearTimeout,
    });

    const beforeAuth = client.connectStateEvents({
      onStateChanged: event => changed.push(event.entityId),
      onDisconnect: () => undefined,
    });
    sockets[0].emit('close');
    await assert.rejects(beforeAuth, (error: unknown) =>
      error instanceof HomeAssistantClientError && error.code === 'network');
    assert.equal(clock.pendingCount, 0);

    const beforeSubscription = client.connectStateEvents({
      onStateChanged: event => changed.push(event.entityId),
      onDisconnect: () => undefined,
    });
    sockets[1].message({type: 'auth_required'});
    sockets[1].message({type: 'auth_ok'});
    sockets[1].emit('close');
    await assert.rejects(beforeSubscription, (error: unknown) =>
      error instanceof HomeAssistantClientError && error.code === 'network');
    assert.equal(clock.pendingCount, 0);

    const reconnected = client.connectStateEvents({
      onStateChanged: event => changed.push(event.entityId),
      onDisconnect: () => undefined,
    });
    const subscription = await finishSubscription(sockets[2], reconnected);
    sockets[2].message(stateEvent());
    assert.deepEqual(changed, ['media_player.kitchen']);
    subscription.close();
    assert.equal(clock.pendingCount, 0);
  }

  {
    const socket = new FakeSocket();
    const client = new HomeAssistantClient({
      token: 'rejected-secret',
      webSocketFactory: () => socket,
    });
    const connected = client.connectStateEvents({
      onStateChanged: () => undefined,
      onDisconnect: () => undefined,
    });
    socket.message({type: 'auth_invalid', message: 'rejected-secret'});
    await assert.rejects(
      connected,
      (error: unknown) => error instanceof HomeAssistantClientError &&
        error.code === 'authentication' &&
        !error.message.includes('rejected-secret')
    );
  }
};

run().catch(error => {
  console.error(error);
  process.exit(1);
});
