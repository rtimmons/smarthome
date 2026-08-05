import {EventEmitter} from 'node:events';
import {Server} from 'node:http';
import {describe, expect, it, vi} from 'vitest';

import {installGracefulShutdown} from './graceful-shutdown';

describe('installGracefulShutdown', () => {
  it('closes the server and exits cleanly on SIGTERM', () => {
    const signalBus = new EventEmitter();
    const close = vi.fn((callback: (error?: Error) => void) => callback());
    const closeIdleConnections = vi.fn();
    const exit = vi.fn();
    const log = vi.fn();
    const server = {close, closeIdleConnections} as unknown as Server;

    const uninstall = installGracefulShutdown(server, {
      service: 'test-service',
      exit,
      log,
      signalTarget: signalBus as unknown as Pick<
        NodeJS.Process,
        'once' | 'removeListener'
      >,
    });
    signalBus.emit('SIGTERM');
    uninstall();

    expect(close).toHaveBeenCalledOnce();
    expect(closeIdleConnections).toHaveBeenCalledOnce();
    expect(exit).toHaveBeenCalledWith(0);
    expect(log).toHaveBeenCalledTimes(2);
  });
});
