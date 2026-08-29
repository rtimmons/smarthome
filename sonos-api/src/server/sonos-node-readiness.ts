import {getJson} from './http';
import type {ShadowZoneLike} from './sonos-shadow-compare';

export interface SonosNodeReadinessSnapshot {
  ready: boolean;
  checkedAt: number | null;
  statusCode?: number;
  error?: string;
}

export type SonosNodeZonesReader = (
  url: string
) => Promise<{statusCode: number; body: ShadowZoneLike[]}>;

export interface SonosNodeReadinessMonitorOptions {
  readZones?: SonosNodeZonesReader;
  now?: () => number;
  intervalMs?: number;
  setInterval?: (callback: () => void, intervalMs: number) => unknown;
  clearInterval?: (handle: unknown) => void;
}

export interface SonosNodeReadinessMonitor {
  start(): Promise<void>;
  stop(): Promise<void>;
  check(): Promise<void>;
  snapshot(): SonosNodeReadinessSnapshot;
}

const defaultReadZones: SonosNodeZonesReader = async url => {
  const response = await getJson<ShadowZoneLike[]>(url, 10_000);
  return {statusCode: response.statusCode, body: response.body};
};

export const createSonosNodeReadinessMonitor = (
  nodeUrl: string,
  options: SonosNodeReadinessMonitorOptions = {}
): SonosNodeReadinessMonitor => {
  const readZones = options.readZones ?? defaultReadZones;
  const now = options.now ?? Date.now;
  const intervalMs = options.intervalMs ?? 5_000;
  const scheduleInterval = options.setInterval ?? ((callback, delay) => setInterval(callback, delay));
  const cancelInterval = options.clearInterval ?? (handle => clearInterval(handle as NodeJS.Timeout));
  let timer: unknown;
  let activeCheck: Promise<void> | null = null;
  let state: SonosNodeReadinessSnapshot = {
    ready: false,
    checkedAt: null,
    error: 'Node Sonos readiness has not been checked',
  };

  const check = (): Promise<void> => {
    if (activeCheck) {
      return activeCheck;
    }
    activeCheck = (async () => {
      try {
        const response = await readZones(`${nodeUrl}/zones`);
        if (response.statusCode < 200 || response.statusCode >= 300) {
          state = {
            ready: false,
            checkedAt: now(),
            statusCode: response.statusCode,
            error: `Node Sonos zones returned HTTP ${response.statusCode}`,
          };
          return;
        }
        if (!Array.isArray(response.body)) {
          state = {
            ready: false,
            checkedAt: now(),
            statusCode: response.statusCode,
            error: 'Node Sonos zones returned an invalid payload',
          };
          return;
        }
        state = {
          ready: true,
          checkedAt: now(),
          statusCode: response.statusCode,
        };
      } catch (error) {
        state = {
          ready: false,
          checkedAt: now(),
          error: error instanceof Error ? error.message : 'Node Sonos readiness check failed',
        };
      } finally {
        activeCheck = null;
      }
    })();
    return activeCheck;
  };

  return {
    start: async () => {
      await check();
      if (timer === undefined) {
        timer = scheduleInterval(() => {
          void check();
        }, intervalMs);
        if (typeof timer === 'object' && timer && 'unref' in timer) {
          (timer as {unref(): void}).unref();
        }
      }
    },
    stop: async () => {
      if (timer !== undefined) {
        cancelInterval(timer);
        timer = undefined;
      }
      if (activeCheck) {
        await activeCheck;
      }
    },
    check,
    snapshot: () => ({...state}),
  };
};
