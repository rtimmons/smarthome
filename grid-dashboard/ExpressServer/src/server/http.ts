export interface HttpResponse {
    statusCode: number;
    body: string;
    headers: Headers;
}

export interface BinaryHttpResponse {
    statusCode: number;
    body: Buffer;
    headers: Headers;
}

export class ResponseBodyTooLargeError extends Error {
    constructor(readonly maximumBytes: number) {
        super(`Upstream response exceeded ${maximumBytes} bytes`);
        this.name = 'ResponseBodyTooLargeError';
    }
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

export const requestBinary = async (
    url: string,
    options: RequestInit = {},
    timeoutMs = 10000,
    maximumBytes = 5 * 1024 * 1024
): Promise<BinaryHttpResponse> => {
    const response = await fetch(url, {
        ...options,
        signal: options.signal || AbortSignal.timeout(timeoutMs),
    });
    const declaredLength = Number(response.headers.get('content-length'));
    if (Number.isFinite(declaredLength) && declaredLength > maximumBytes) {
        await response.body?.cancel();
        throw new ResponseBodyTooLargeError(maximumBytes);
    }

    if (!response.body) {
        return {
            statusCode: response.status,
            body: Buffer.alloc(0),
            headers: response.headers,
        };
    }

    const reader = response.body.getReader();
    const chunks: Buffer[] = [];
    let totalBytes = 0;
    try {
        while (true) {
            const result = await reader.read();
            if (result.done) {
                break;
            }
            const chunk = Buffer.from(result.value);
            totalBytes += chunk.length;
            if (totalBytes > maximumBytes) {
                await reader.cancel();
                throw new ResponseBodyTooLargeError(maximumBytes);
            }
            chunks.push(chunk);
        }
    } finally {
        reader.releaseLock();
    }

    return {
        statusCode: response.status,
        body: Buffer.concat(chunks, totalBytes),
        headers: response.headers,
    };
};
