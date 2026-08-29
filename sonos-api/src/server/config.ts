export type SonosBackendMode = 'node' | 'shadow' | 'home_assistant';

const parsePort = (value: string | undefined, fallback: number): number => {
  const parsed = value ? parseInt(value, 10) : NaN;
  return Number.isFinite(parsed) ? parsed : fallback;
};

const normalizeUrl = (value: string): string => value.replace(/\/+$/, '');

const parseBackendMode = (value: string | undefined): SonosBackendMode => {
  if (value === 'shadow' || value === 'home_assistant') return value;
  return 'node';
};

export const loadAppConfig = (env: NodeJS.ProcessEnv = process.env) => ({
  backendMode: parseBackendMode(env.SONOS_BACKEND_MODE),
  sonosUrl: normalizeUrl(
    env.SONOS_BASE_URL || env.SONOS_URL || 'http://localhost:5005',
  ),
  homeAssistantRestUrl: normalizeUrl(
    env.HOME_ASSISTANT_REST_URL || 'http://supervisor/core/api',
  ),
  homeAssistantWebSocketUrl:
    env.HOME_ASSISTANT_WEBSOCKET_URL || 'ws://supervisor/core/websocket',
  homeAssistantToken: env.SUPERVISOR_TOKEN || env.HOME_ASSISTANT_TOKEN || '',
  port: parsePort(env.PORT || env.APP_PORT, 5006),
});

export const appConfig = loadAppConfig();
