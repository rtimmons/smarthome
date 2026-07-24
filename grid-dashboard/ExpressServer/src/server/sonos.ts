import { Request as RQ, Response as RS, Router } from 'express';

import '../types/sonos';

import { appConfig } from './config';
import { requestText } from './http';

const app = Router();

const proxySonosGet = async (route: string, res: RS): Promise<void> => {
    const url = `${appConfig.sonosUrl}/${route}`;

    try {
        const response = await requestText(url, {
            method: 'GET',
        });

        const contentType =
            response.headers.get('content-type') ||
            'application/json; charset=utf-8';
        const forwardedHeaders = [
            'x-sonos-response-source',
            'x-sonos-response-stale',
            'x-sonos-observed-at',
            'x-sonos-age-ms',
        ];

        forwardedHeaders.forEach(headerName => {
            const headerValue = response.headers.get(headerName);
            if (headerValue) {
                res.setHeader(headerName, headerValue);
            }
        });

        res.type(contentType)
            .status(response.statusCode)
            .send(response.body);
    } catch (err) {
        const message = err instanceof Error ? err.message : 'Sonos API request failed';
        console.error(
            `Sonos API error for ${route}:`,
            message
        );
        res.status(502).json({
            error: message,
            route,
        });
    }
};

const proxySonosRequest = async (
    method: string,
    route: string,
    res: RS,
    body?: unknown
): Promise<void> => {
    const url = `${appConfig.sonosUrl}/${route}`;

    try {
        const response = await requestText(url, {
            method,
            headers: body === undefined ? undefined : {'Content-Type': 'application/json'},
            body: body === undefined ? undefined : JSON.stringify(body),
        });

        res.type(response.headers.get('content-type') || 'application/json')
            .status(response.statusCode)
            .send(response.body);
    } catch (err) {
        const message = err instanceof Error ? err.message : 'Sonos API request failed';
        console.error(
            `Sonos API error for ${method} ${route}:`,
            message
        );
        res.status(502).json({
            error: message,
            route,
        });
    }
};

const sonosGet = (
    routeFactory: string | ((req: RQ) => string)
): ((req: RQ, res: RS) => Promise<void>) => {
    return async (req: RQ, res: RS) => {
        const route =
            typeof routeFactory === 'function'
                ? routeFactory(req)
                : routeFactory;
        await proxySonosGet(route, res);
    };
};

app.get('/pause', sonosGet('pause'));
app.get('/play', sonosGet('play'));
app.get('/tv', sonosGet('preset/all-tv'));
app.get('/07', sonosGet('favorite/Zero 7 Radio'));
app.get('/quiet', sonosGet('groupVolume/7'));
app.post('/sonos-intents/group-all', async (req: RQ, res: RS) => {
    await proxySonosRequest('POST', 'intents/sonos/group-all', res, req.body);
});
app.get('/sonos-intents/status', async (_req: RQ, res: RS) => {
    await proxySonosRequest('GET', 'intents/sonos/status', res);
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

        const rest = match[1];
        await proxySonosGet(`sonos/${rest}`, res);
    });
})();

// Custom routes /same/:room, /down, /up are now handled by sonos-api add-on
// Simple proxy routes below forward to sonos-api which has the business logic
app.get('/same/:room', sonosGet((req: RQ) => `same/${req.params.room}`));
app.get('/down', sonosGet('down'));
app.get('/up', sonosGet('up'));

export const sonos = app;
