import {Server} from 'node:http';

export interface GracefulShutdownOptions {
  service: string;
  timeoutMs?: number;
  drainTimeoutMs?: number;
  signals?: NodeJS.Signals[];
  exit?: (code: number) => void;
  log?: (message: string) => void;
  signalTarget?: Pick<NodeJS.Process, 'once' | 'removeListener'>;
  beforeClose?: () => void | Promise<void>;
}

export function installGracefulShutdown(
  server: Server,
  options: GracefulShutdownOptions,
): () => void {
  const timeoutMs = options.timeoutMs ?? 5_000;
  const drainTimeoutMs = options.drainTimeoutMs ?? 250;
  const signals = options.signals ?? ['SIGTERM', 'SIGINT'];
  const exit = options.exit ?? ((code: number) => process.exit(code));
  const log = options.log ?? console.log;
  const signalTarget = options.signalTarget ?? process;
  let shuttingDown = false;

  const handlers = new Map<NodeJS.Signals, () => void>();

  for (const signal of signals) {
    const handler = () => {
      if (shuttingDown) return;
      shuttingDown = true;
      const started = performance.now();
      log(
        JSON.stringify({
          event: 'service.shutdown.started',
          service: options.service,
          signal,
          pid: process.pid,
          uptimeSeconds: Number(process.uptime().toFixed(3)),
        }),
      );

      const forceTimer = setTimeout(() => {
        server.closeAllConnections?.();
        log(
          JSON.stringify({
            event: 'service.shutdown.forced',
            service: options.service,
            signal,
            elapsedMs: Math.round(performance.now() - started),
          }),
        );
        exit(1);
      }, timeoutMs);
      forceTimer.unref();

      // Give active requests a short drain window, then close persistent
      // connections that would otherwise hold shutdown until the force timer.
      const drainTimer = setTimeout(() => {
        server.closeAllConnections?.();
      }, drainTimeoutMs);
      drainTimer.unref();

      let serverClosed = false;
      let cleanupCompleted = !options.beforeClose;
      let shutdownError: Error | undefined;
      const completeIfReady = () => {
        if (!serverClosed || !cleanupCompleted) return;
        clearTimeout(forceTimer);
        clearTimeout(drainTimer);
        log(
          JSON.stringify({
            event: 'service.shutdown.completed',
            service: options.service,
            signal,
            elapsedMs: Math.round(performance.now() - started),
            status: shutdownError ? 'error' : 'ok',
            error: shutdownError?.message,
          }),
        );
        exit(shutdownError ? 1 : 0);
      };

      server.close((error?: Error) => {
        serverClosed = true;
        shutdownError = error || shutdownError;
        completeIfReady();
      });
      server.closeIdleConnections?.();

      if (options.beforeClose) {
        Promise.resolve()
          .then(options.beforeClose)
          .catch(error => {
            shutdownError = error instanceof Error
              ? error
              : new Error('Shutdown cleanup failed');
          })
          .finally(() => {
            cleanupCompleted = true;
            completeIfReady();
          });
      }
    };
    handlers.set(signal, handler);
    signalTarget.once(signal, handler);
  }

  return () => {
    for (const [signal, handler] of handlers) {
      signalTarget.removeListener(signal, handler);
    }
  };
}
