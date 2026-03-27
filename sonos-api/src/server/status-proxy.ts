import rpn = require('request-promise-native');

export interface SonosStatusProxyOptions {
  cacheTtlMs?: number;
  requestTimeoutMs?: number;
  now?: () => number;
  request?: SonosRequestFn;
}

export interface SonosProxyResponse {
  statusCode: number;
  body: string;
  contentType: string;
  headers: {[key: string]: string};
}

interface CacheEntry {
  body: string;
  insertedAt: number;
  contentType: string;
}

interface UpstreamResponse {
  statusCode: number;
  body: unknown;
  headers?: {[key: string]: string | string[] | undefined};
}

interface UpstreamRequestOptions {
  method: 'GET';
  uri: string;
  resolveWithFullResponse: boolean;
  simple: boolean;
  timeout: number;
}

type SonosRequestFn = (options: UpstreamRequestOptions) => Promise<UpstreamResponse>;

const DEFAULT_CACHE_TTL_MS = 30 * 1000;
const DEFAULT_REQUEST_TIMEOUT_MS = 900;
const DEFAULT_CONTENT_TYPE = 'application/json; charset=utf-8';

const HEADER_SOURCE = 'X-Sonos-Response-Source';
const HEADER_STALE = 'X-Sonos-Response-Stale';
const HEADER_OBSERVED_AT = 'X-Sonos-Observed-At';
const HEADER_AGE_MS = 'X-Sonos-Age-Ms';

const TRANSIENT_CODES: {[key: string]: boolean} = {
  ECONNREFUSED: true,
  ECONNRESET: true,
  EHOSTUNREACH: true,
  ENETUNREACH: true,
  ESOCKETTIMEDOUT: true,
  ETIMEDOUT: true,
};

const isCacheableRoute = (route: string): boolean => {
  return route === 'zones' || /^[^/]+\/state$/.test(route);
};

const normalizeContentType = (
  headers: {[key: string]: string | string[] | undefined} | undefined
): string => {
  if (!headers) {
    return DEFAULT_CONTENT_TYPE;
  }

  const value = headers['content-type'] || headers['Content-Type'];
  if (Array.isArray(value)) {
    return value[0] || DEFAULT_CONTENT_TYPE;
  }
  return value || DEFAULT_CONTENT_TYPE;
};

const serializeBody = (body: unknown): string => {
  if (typeof body === 'string') {
    return body;
  }
  return JSON.stringify(body);
};

const upstreamErrorCode = (err: any): string => {
  return String(
    (err && err.cause && err.cause.code) ||
    (err && err.error && err.error.code) ||
    (err && err.code) ||
    ''
  );
};

const upstreamErrorMessage = (err: any): string => {
  if (err && typeof err.message === 'string' && err.message.trim().length > 0) {
    return err.message.trim();
  }
  return 'Sonos upstream request failed';
};

const isTransientReadError = (err: any): boolean => {
  const code = upstreamErrorCode(err);
  if (code && TRANSIENT_CODES[code]) {
    return true;
  }

  const message = upstreamErrorMessage(err);
  return message.indexOf('AggregateError') >= 0 || message.indexOf('timed out') >= 0;
};

const responseHeaders = (source: 'live' | 'cache', insertedAt: number, now: number): {[key: string]: string} => {
  return {
    [HEADER_SOURCE]: source,
    [HEADER_STALE]: source === 'cache' ? 'true' : 'false',
    [HEADER_OBSERVED_AT]: new Date(insertedAt).toISOString(),
    [HEADER_AGE_MS]: String(Math.max(0, now - insertedAt)),
  };
};

export class SonosStatusProxy {
  private readonly cacheTtlMs: number;
  private readonly requestTimeoutMs: number;
  private readonly now: () => number;
  private readonly request: SonosRequestFn;
  private readonly cache: {[key: string]: CacheEntry} = {};
  private readonly inflight: {[key: string]: Promise<SonosProxyResponse>} = {};

  constructor(options: SonosStatusProxyOptions = {}) {
    this.cacheTtlMs = options.cacheTtlMs || DEFAULT_CACHE_TTL_MS;
    this.requestTimeoutMs = options.requestTimeoutMs || DEFAULT_REQUEST_TIMEOUT_MS;
    this.now = options.now || (() => Date.now());
    this.request = options.request || rpn;
  }

  async get(baseUrl: string, route: string): Promise<SonosProxyResponse> {
    if (!isCacheableRoute(route)) {
      return this.fetchLive(baseUrl, route);
    }

    const existing = this.inflight[route];
    if (existing) {
      return existing;
    }

    const pending = this.fetchCacheable(baseUrl, route)
      .finally(() => {
        delete this.inflight[route];
      });
    this.inflight[route] = pending;
    return pending;
  }

  invalidate(route?: string): void {
    if (route) {
      delete this.cache[route];
      delete this.inflight[route];
      return;
    }

    Object.keys(this.cache).forEach(key => delete this.cache[key]);
    Object.keys(this.inflight).forEach(key => delete this.inflight[key]);
  }

  private async fetchCacheable(baseUrl: string, route: string): Promise<SonosProxyResponse> {
    try {
      return await this.fetchLive(baseUrl, route);
    } catch (err) {
      const cached = this.cache[route];
      const now = this.now();
      const ageMs = cached ? now - cached.insertedAt : Number.MAX_SAFE_INTEGER;
      const canServeStale = Boolean(cached && ageMs <= this.cacheTtlMs);

      if (canServeStale) {
        console.warn(
          `Sonos API served stale ${route} after transient upstream failure (${upstreamErrorCode(err) || upstreamErrorMessage(err)}), age=${ageMs}ms`
        );
        return {
          statusCode: 200,
          body: cached.body,
          contentType: cached.contentType,
          headers: responseHeaders('cache', cached.insertedAt, now),
        };
      }

      throw err;
    }
  }

  private async fetchLive(baseUrl: string, route: string): Promise<SonosProxyResponse> {
    const now = this.now();
    try {
      const response = await this.request({
        method: 'GET',
        uri: `${baseUrl}/${route}`,
        resolveWithFullResponse: true,
        simple: false,
        timeout: this.requestTimeoutMs,
      }) as UpstreamResponse;
      const body = serializeBody(response.body);
      const contentType = normalizeContentType(response.headers);

      if (isCacheableRoute(route) && response.statusCode >= 200 && response.statusCode < 300) {
        this.cache[route] = {
          body,
          insertedAt: now,
          contentType,
        };
      }

      return {
        statusCode: response.statusCode,
        body,
        contentType,
        headers: responseHeaders('live', now, now),
      };
    } catch (err) {
      if (isCacheableRoute(route) && isTransientReadError(err)) {
        console.warn(
          `Sonos API transient upstream ${route} failure: ${upstreamErrorCode(err) || upstreamErrorMessage(err)}`
        );
      }
      throw err;
    }
  }
}

export const sonosResponseHeaderNames = {
  source: HEADER_SOURCE,
  stale: HEADER_STALE,
  observedAt: HEADER_OBSERVED_AT,
  ageMs: HEADER_AGE_MS,
};
