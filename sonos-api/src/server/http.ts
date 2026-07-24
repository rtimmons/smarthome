export interface HttpResponse {
  statusCode: number;
  body: string;
  headers: {[key: string]: string};
}

const DEFAULT_TIMEOUT_MS = 5000;

export const getText = async (
  uri: string,
  timeoutMs = DEFAULT_TIMEOUT_MS
): Promise<HttpResponse> => {
  let response: Response;
  try {
    response = await fetch(uri, {
      method: 'GET',
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (err) {
    if (err instanceof Error && err.name === 'TimeoutError') {
      const timeoutError = new Error(`Sonos upstream request timed out after ${timeoutMs}ms`) as Error & {
        code: string;
      };
      timeoutError.code = 'ETIMEDOUT';
      throw timeoutError;
    }
    throw err;
  }

  return {
    statusCode: response.status,
    body: await response.text(),
    headers: Object.fromEntries(response.headers.entries()),
  };
};

export const getJson = async <T>(
  uri: string,
  timeoutMs = DEFAULT_TIMEOUT_MS
): Promise<{statusCode: number; body: T; headers: {[key: string]: string}}> => {
  const response = await getText(uri, timeoutMs);
  return {
    ...response,
    body: JSON.parse(response.body) as T,
  };
};
