const env = process.env;

const parsePort = (value: string | undefined, fallback: number): number => {
  const parsed = value ? parseInt(value, 10) : NaN;
  return Number.isFinite(parsed) ? parsed : fallback;
};

export const appConfig = {
  sonosUrl: env.SONOS_BASE_URL || env.SONOS_URL || 'http://localhost:5005',
  port: parsePort(env.PORT || env.APP_PORT, 5006),
};
