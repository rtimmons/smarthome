import assert from 'node:assert/strict';
import {EventEmitter} from 'node:events';
import {Server} from 'node:http';
import test from 'node:test';

import {installGracefulShutdown} from './graceful-shutdown';

test('graceful shutdown closes the server and exits cleanly', () => {
  const signalBus = new EventEmitter();
  let closeCalls = 0;
  let closeIdleCalls = 0;
  const exitCodes: number[] = [];
  const logs: string[] = [];
  const server = {
    close(callback: (error?: Error) => void) {
      closeCalls += 1;
      callback();
    },
    closeIdleConnections() {
      closeIdleCalls += 1;
    },
  } as unknown as Server;

  const uninstall = installGracefulShutdown(server, {
    service: 'test-service',
    exit: (code) => exitCodes.push(code),
    log: (message) => logs.push(message),
    signalTarget: signalBus as unknown as Pick<
      NodeJS.Process,
      'once' | 'removeListener'
    >,
  });
  signalBus.emit('SIGTERM');
  uninstall();

  assert.equal(closeCalls, 1);
  assert.equal(closeIdleCalls, 1);
  assert.deepEqual(exitCodes, [0]);
  assert.equal(logs.length, 2);
});

test('graceful shutdown closes persistent connections after the drain window', async () => {
  const signalBus = new EventEmitter();
  const exitCodes: number[] = [];
  let closeCallback: ((error?: Error) => void) | undefined;
  let closeAllCalls = 0;
  const server = {
    close(callback: (error?: Error) => void) {
      closeCallback = callback;
    },
    closeIdleConnections() {},
    closeAllConnections() {
      closeAllCalls += 1;
      closeCallback?.();
    },
  } as unknown as Server;

  installGracefulShutdown(server, {
    service: 'test-service',
    drainTimeoutMs: 1,
    exit: (code) => exitCodes.push(code),
    log: () => {},
    signalTarget: signalBus as unknown as Pick<
      NodeJS.Process,
      'once' | 'removeListener'
    >,
  });
  signalBus.emit('SIGTERM');
  await new Promise((resolve) => setTimeout(resolve, 10));

  assert.equal(closeAllCalls, 1);
  assert.deepEqual(exitCodes, [0]);
});
