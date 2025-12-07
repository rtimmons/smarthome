export interface AppConfig {
  port: number;
  host: string;
  mongoUrl: string;
  mongoRetries: number;
  mongoRetryDelayMs: number;
  publicBaseUrl?: string;
}

const DEFAULT_PORT = 4100;
const DEFAULT_HOST = "0.0.0.0";
// Supervisor DNS exposes add-ons as addon_<slug>; for a locally added add-on the slug is prefixed with "local_".
// Use addon_local_mongodb as the default host for the bundled MongoDB add-on.
const DEFAULT_MONGO = "mongodb://addon_local_mongodb:27017/tinyurl";
const DEFAULT_MONGO_RETRIES = 20;
const DEFAULT_MONGO_RETRY_DELAY_MS = 2000;

export function loadConfig(): AppConfig {
  const port = parseInt(process.env.PORT || `${DEFAULT_PORT}`, 10);
  const host = process.env.HOST || DEFAULT_HOST;
  const mongoUrl = process.env.MONGODB_URL || DEFAULT_MONGO;
  const mongoRetries = parseInt(process.env.MONGO_RETRY_ATTEMPTS || `${DEFAULT_MONGO_RETRIES}`, 10);
  const mongoRetryDelayMs = parseInt(
    process.env.MONGO_RETRY_DELAY_MS || `${DEFAULT_MONGO_RETRY_DELAY_MS}`,
    10,
  );
  const publicBaseUrl = process.env.PUBLIC_BASE_URL;

  return { port, host, mongoUrl, mongoRetries, mongoRetryDelayMs, publicBaseUrl };
}
