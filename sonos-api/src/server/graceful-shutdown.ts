import {Server} from 'node:http';

export interface GracefulShutdownOptions {
  service: string;
  timeoutMs?: number;
  drainTimeoutMs?: number;
  signals?: NodeJS.Signals[];
  exit?: (code: number) => void;
  log?: (message: string) => void;
  signalTarget?: Pick<NodeJS.Process, 'once' | 'removeListener'>;
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

      server.close((error?: Error) => {
        clearTimeout(forceTimer);
        clearTimeout(drainTimer);
        log(
          JSON.stringify({
            event: 'service.shutdown.completed',
            service: options.service,
            signal,
            elapsedMs: Math.round(performance.now() - started),
            status: error ? 'error' : 'ok',
            error: error?.message,
          }),
        );
        exit(error ? 1 : 0);
      });
      server.closeIdleConnections?.();
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
