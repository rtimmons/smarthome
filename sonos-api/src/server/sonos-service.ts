import {Router} from 'express';

import type {SonosBackendMode} from './config';
import {HomeAssistantClient} from './home-assistant-client';
import {
  createHomeAssistantSonosRouter,
  HomeAssistantSonosRuntime,
} from './home-assistant-sonos-runtime';
import {HomeAssistantStateStore} from './home-assistant-state-store';
import {getJson} from './http';
import {sonos as nodeSonosRouter} from './sonos';
import {
  createSonosNodeReadinessMonitor,
  type SonosNodeReadinessMonitor,
  type SonosNodeZonesReader,
} from './sonos-node-readiness';
import {
  compareSonosBackends,
  SonosShadowPersistenceTracker,
  type ShadowZoneLike,
} from './sonos-shadow-compare';

export interface SonosServiceConfig {
  backendMode: SonosBackendMode;
  sonosUrl: string;
  homeAssistantRestUrl: string;
  homeAssistantWebSocketUrl: string;
  homeAssistantToken: string;
}

export interface SonosServiceHealth {
  statusCode: number;
  body: Record<string, unknown>;
}

export interface SelectedSonosService {
  router: Router;
  start(): Promise<void>;
  stop(): Promise<void>;
  health(): SonosServiceHealth;
}

interface SonosServiceLogger {
  log(message: string): void;
  warn(message: string): void;
}

export interface SonosServiceDependencies {
  nodeRouter?: Router;
  createHomeAssistantRuntime?: (
    config: SonosServiceConfig
  ) => HomeAssistantSonosRuntime;
  createHomeAssistantRouter?: typeof createHomeAssistantSonosRouter;
  createNodeReadinessMonitor?: (
    nodeUrl: string
  ) => SonosNodeReadinessMonitor;
  readNodeZones?: SonosNodeZonesReader;
  now?: () => number;
  logger?: SonosServiceLogger;
  shadowGraceMs?: number;
  shadowPollIntervalMs?: number;
}

export interface ShadowObserverOptions {
  readNodeZones?: SonosNodeZonesReader;
  now?: () => number;
  logger?: SonosServiceLogger;
  graceMs?: number;
  pollIntervalMs?: number;
}

const unavailableRouter = (message: string): Router => {
  const router = Router();
  router.use((_req, res) => {
    res.status(503).json({
      error: message,
      code: 'home_assistant_not_configured',
      retryable: true,
    });
  });
  return router;
};

export const createShadowObserver = (
  runtime: HomeAssistantSonosRuntime,
  nodeUrl: string,
  options: ShadowObserverOptions = {}
): (() => Promise<void>) => {
  const now = options.now ?? Date.now;
  const logger = options.logger ?? console;
  const graceMs = options.graceMs ?? 5_000;
  const pollIntervalMs = options.pollIntervalMs ?? 5_000;
  const readNodeZones = options.readNodeZones ?? (async url => {
    const response = await getJson<ShadowZoneLike[]>(url, 10_000);
    return {statusCode: response.statusCode, body: response.body};
  });
  const persistence = new SonosShadowPersistenceTracker({graceMs, now});
  let lastStartedAt: number | null = null;
  let active: Promise<void> | null = null;
  return async (): Promise<void> => {
    const current = now();
    if (active) {
      return active;
    }
    if (lastStartedAt !== null && current - lastStartedAt < pollIntervalMs) {
      return;
    }
    lastStartedAt = current;
    active = (async () => {
      try {
        const node = await readNodeZones(`${nodeUrl}/zones`);
        if (node.statusCode < 200 || node.statusCode >= 300) {
          logger.warn(JSON.stringify({
            event: 'sonos_shadow_read_failed',
            statusCode: node.statusCode,
          }));
          return;
        }
        const homeAssistant = runtime.zones() as ShadowZoneLike[];
        const comparison = compareSonosBackends(node.body, homeAssistant);
        const assessment = persistence.observe(comparison.differences);
        if (comparison.equal) {
          logger.log(JSON.stringify({
            event: 'sonos_shadow_comparison',
            equal: true,
            differenceCount: 0,
          }));
        } else if (assessment.newlyPersistentDifferences.length > 0) {
          logger.warn(JSON.stringify({
            event: 'sonos_shadow_persistent_difference',
            equal: false,
            graceMs,
            persistentForMs: assessment.oldestPersistentAgeMs,
            differenceCount: assessment.persistentDifferences.length,
            differences: assessment.persistentDifferences,
          }));
        }
      } catch (error) {
        logger.warn(JSON.stringify({
          event: 'sonos_shadow_comparison_failed',
          error: error instanceof Error ? error.message : 'unknown shadow failure',
        }));
      } finally {
        active = null;
      }
    })();
    return active;
  };
};

export const createSonosService = (
  config: SonosServiceConfig,
  dependencies: SonosServiceDependencies = {}
): SelectedSonosService => {
  const nodeRouter = dependencies.nodeRouter ?? nodeSonosRouter;
  const nodeReadiness = dependencies.createNodeReadinessMonitor
    ? dependencies.createNodeReadinessMonitor(config.sonosUrl)
    : createSonosNodeReadinessMonitor(config.sonosUrl, {
      readZones: dependencies.readNodeZones,
      now: dependencies.now,
    });

  if (config.backendMode === 'node') {
    return {
      router: nodeRouter,
      start: () => nodeReadiness.start(),
      stop: () => nodeReadiness.stop(),
      health: () => {
        const node = nodeReadiness.snapshot();
        return {
          statusCode: node.ready ? 200 : 503,
          body: {
            status: node.ready ? 'ok' : 'not_ready',
            ready: node.ready,
            backendMode: 'node',
            node,
          },
        };
      },
    };
  }

  let runtime: HomeAssistantSonosRuntime | null = null;
  let configurationError: string | null = null;
  try {
    if (dependencies.createHomeAssistantRuntime) {
      runtime = dependencies.createHomeAssistantRuntime(config);
    } else {
      const client = new HomeAssistantClient({
        token: config.homeAssistantToken,
        restBaseUrl: config.homeAssistantRestUrl,
        websocketUrl: config.homeAssistantWebSocketUrl,
        requestTimeoutMs: 10_000,
        websocketTimeoutMs: 10_000,
      });
      const stateStore = new HomeAssistantStateStore({client});
      runtime = new HomeAssistantSonosRuntime({client, stateStore});
    }
  } catch (error) {
    configurationError = error instanceof Error
      ? error.message
      : 'Home Assistant Sonos backend configuration failed';
  }

  if (config.backendMode === 'shadow') {
    const router = Router();
    let runtimeStartError: string | null = null;
    const observe = runtime
      ? createShadowObserver(runtime, config.sonosUrl, {
        readNodeZones: dependencies.readNodeZones,
        now: dependencies.now,
        logger: dependencies.logger,
        graceMs: dependencies.shadowGraceMs,
        pollIntervalMs: dependencies.shadowPollIntervalMs,
      })
      : async () => undefined;
    router.use((req, _res, next) => {
      if (req.method === 'GET' &&
          (req.path === '/sonos/zones' || /\/sonos\/[^/]+\/state$/.test(req.path))) {
        void observe();
      }
      next();
    });
    router.use(nodeRouter);
    return {
      router,
      start: async () => {
        await nodeReadiness.start();
        if (runtime) {
          try {
            await runtime.start();
            runtimeStartError = null;
          } catch (error) {
            runtimeStartError = error instanceof Error
              ? error.message
              : 'Home Assistant shadow observer failed to start';
          }
        }
      },
      stop: async () => {
        runtime?.stop();
        await nodeReadiness.stop();
      },
      health: () => {
        const node = nodeReadiness.snapshot();
        const homeAssistant = runtime
          ? {
            ...runtime.health(),
            ...(runtimeStartError
              ? {ready: false, error: runtimeStartError}
              : {}),
          }
          : {ready: false, error: configurationError};
        return {
          statusCode: node.ready ? 200 : 503,
          body: {
            status: node.ready ? 'ok' : 'not_ready',
            ready: node.ready,
            backendMode: 'shadow',
            node,
            homeAssistant,
          },
        };
      },
    };
  }

  if (!runtime) {
    const message = configurationError || 'Home Assistant Sonos backend is unavailable';
    return {
      router: unavailableRouter(message),
      start: async () => undefined,
      stop: async () => undefined,
      health: () => ({
        statusCode: 503,
        body: {
          status: 'not_ready',
          ready: false,
          backendMode: 'home_assistant',
          error: message,
        },
      }),
    };
  }

  return {
    router: (dependencies.createHomeAssistantRouter ?? createHomeAssistantSonosRouter)(runtime),
    start: () => runtime.start(),
    stop: async () => runtime.stop(),
    health: () => {
      const state = runtime.health();
      return {
        statusCode: state.ready ? 200 : 503,
        body: {
          status: state.ready ? 'ok' : 'not_ready',
          ready: state.ready,
          backendMode: 'home_assistant',
          homeAssistant: state,
        },
      };
    },
  };
};
