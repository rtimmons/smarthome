export interface HttpResponse {
    statusCode: number;
    body: string;
    headers: Headers;
}

export const requestText = async (
    url: string,
    options: RequestInit = {},
    timeoutMs = 10000
): Promise<HttpResponse> => {
    const response = await fetch(url, {
        ...options,
        signal: options.signal || AbortSignal.timeout(timeoutMs),
    });

    return {
        statusCode: response.status,
        body: await response.text(),
        headers: response.headers,
    };
};
