import {Request as RQ, Response as RS, Router} from 'express';

import '../types/sonos';

import {appConfig} from './config';
import {
    requestBinary,
    requestText,
    type BinaryHttpResponse,
    type HttpResponse,
} from './http';

export const SONOS_ARTWORK_MAX_BYTES = 5 * 1024 * 1024;
export const SONOS_INTENT_UPSTREAM_ROUTES = Object.freeze({
    groupAll: 'intents/sonos/group-all',
    status: 'intents/sonos/status',
});
export const SONOS_DEPRECATED_ROOT_ROUTES = Object.freeze([
    'pause',
    'play',
    'tv',
    '07',
    'quiet',
]);

type TextRequester = (
    url: string,
    options?: RequestInit,
    timeoutMs?: number
) => Promise<HttpResponse>;
type BinaryRequester = (
    url: string,
    options?: RequestInit,
    timeoutMs?: number,
    maximumBytes?: number
) => Promise<BinaryHttpResponse>;

export interface SonosRouterDependencies {
    sonosUrl?: string;
    requestText?: TextRequester;
    requestBinary?: BinaryRequester;
    artworkMaximumBytes?: number;
}

export interface SonosProxy {
    get(route: string, res: RS): Promise<void>;
    request(
        method: string,
        route: string,
        res: RS,
        body?: unknown
    ): Promise<void>;
}

const freshnessHeaders = [
    'x-sonos-response-source',
    'x-sonos-response-stale',
    'x-sonos-observed-at',
    'x-sonos-age-ms',
    'x-sonos-unavailable-rooms',
];

const artworkHeaders = freshnessHeaders.concat([
    'cache-control',
    'etag',
    'last-modified',
]);

const safeArtworkTypes: {[contentType: string]: boolean} = {
    'image/gif': true,
    'image/jpeg': true,
    'image/png': true,
    'image/webp': true,
};

const normalizedMediaType = (contentType: string | null): string => {
    return String(contentType || '')
        .split(';')[0]
        .trim()
        .toLowerCase();
};

const isArtworkRoute = (route: string): boolean => {
    return /^sonos\/[^/]+\/artwork$/.test(route);
};

const forwardHeaders = (
    res: RS,
    headers: Headers,
    names: string[]
): void => {
    names.forEach(headerName => {
        const headerValue = headers.get(headerName);
        if (headerValue !== null) {
            res.setHeader(headerName, headerValue);
        }
    });
};

const sendProxyFailure = (
    res: RS,
    route: string,
    err: unknown,
    method?: string
): void => {
    const message = err instanceof Error ? err.message : 'Sonos API request failed';
    console.error(
        `Sonos API error for ${method ? `${method} ` : ''}${route}:`,
        message
    );
    res.status(502).json({
        error: message,
        route,
    });
};

export const createSonosProxy = (
    dependencies: SonosRouterDependencies = {}
): SonosProxy => {
    const sonosUrl = dependencies.sonosUrl || appConfig.sonosUrl;
    const fetchText = dependencies.requestText || requestText;
    const fetchBinary = dependencies.requestBinary || requestBinary;
    const artworkMaximumBytes =
        dependencies.artworkMaximumBytes || SONOS_ARTWORK_MAX_BYTES;

    const proxySonosGet = async (route: string, res: RS): Promise<void> => {
        const url = `${sonosUrl}/${route}`;

        try {
            if (isArtworkRoute(route)) {
                const response = await fetchBinary(
                    url,
                    {method: 'GET'},
                    10000,
                    artworkMaximumBytes
                );
                const contentType =
                    response.headers.get('content-type') ||
                    'application/octet-stream';
                if (
                    response.statusCode >= 200 &&
                    response.statusCode < 300 &&
                    !safeArtworkTypes[normalizedMediaType(contentType)]
                ) {
                    throw new Error('Sonos artwork response was not a safe raster image');
                }

                forwardHeaders(res, response.headers, artworkHeaders);
                res.setHeader('Content-Type', contentType);
                res.setHeader('X-Content-Type-Options', 'nosniff');
                res.status(response.statusCode).send(response.body);
                return;
            }

            const response = await fetchText(url, {method: 'GET'});
            const contentType =
                response.headers.get('content-type') ||
                'application/json; charset=utf-8';
            forwardHeaders(res, response.headers, freshnessHeaders);
            res.type(contentType).status(response.statusCode).send(response.body);
        } catch (err) {
            sendProxyFailure(res, route, err);
        }
    };

    const proxySonosRequest = async (
        method: string,
        route: string,
        res: RS,
        body?: unknown
    ): Promise<void> => {
        const url = `${sonosUrl}/${route}`;

        try {
            const response = await fetchText(url, {
                method,
                headers:
                    body === undefined
                        ? undefined
                        : {'Content-Type': 'application/json'},
                body: body === undefined ? undefined : JSON.stringify(body),
            });

            res.type(response.headers.get('content-type') || 'application/json')
                .status(response.statusCode)
                .send(response.body);
        } catch (err) {
            sendProxyFailure(res, route, err, method);
        }
    };

    return {
        get: proxySonosGet,
        request: proxySonosRequest,
    };
};

export const createSonosRouter = (
    dependencies: SonosRouterDependencies = {}
): Router => {
    const app = Router();
    const proxy = createSonosProxy(dependencies);

    const sonosGet = (
        routeFactory: string | ((req: RQ) => string)
    ): ((req: RQ, res: RS) => Promise<void>) => {
        return async (req: RQ, res: RS) => {
            const route =
                typeof routeFactory === 'function'
                    ? routeFactory(req)
                    : routeFactory;
            await proxy.get(route, res);
        };
    };

    for (const route of SONOS_DEPRECATED_ROOT_ROUTES) {
        // Keep these as exact pass-throughs. The compatibility service owns
        // mode-aware deprecation, including the normalized 410 response in
        // Home Assistant mode and legacy behavior in node rollback mode.
        app.get(`/${route}`, sonosGet(route));
    }
    app.post('/sonos-intents/group-all', async (req: RQ, res: RS) => {
        await proxy.request(
            'POST',
            SONOS_INTENT_UPSTREAM_ROUTES.groupAll,
            res,
            req.body
        );
    });
    app.get('/sonos-intents/status', async (_req: RQ, res: RS) => {
        await proxy.request(
            'GET',
            SONOS_INTENT_UPSTREAM_ROUTES.status,
            res
        );
    });

    (() => {
        const rex: RegExp = /sonos\/(.*)$/;
        app.get(rex, async (req: RQ, res: RS) => {
            const match = req.path.match(rex);
            if (match === null) {
                res.status(400).json({
                    error: `Invalid sonos request ${req.path}`,
                });
                return;
            }

            await proxy.get(`sonos/${match[1]}`, res);
        });
    })();

    app.get(
        '/same/:room',
        sonosGet((req: RQ) => {
            const roomParam = req.params.room;
            const room = Array.isArray(roomParam) ? roomParam[0] : roomParam;
            return `same/${encodeURIComponent(room || '')}`;
        })
    );
    app.get('/down', sonosGet('down'));
    app.get('/up', sonosGet('up'));

    return app;
};

export const sonos = createSonosRouter();
