import { Request as RQ, Response as RS, Router } from 'express';
import * as rpn from 'request-promise-native';

import '../types/sonos';

import { appConfig } from './config';

const app = Router();

const proxySonosGet = async (route: string, res: RS): Promise<void> => {
    const url = `${appConfig.sonosUrl}/${route}`;

    try {
        const response = await rpn({
            method: 'GET',
            uri: url,
            resolveWithFullResponse: true,
            simple: false,
        });

        const contentType =
            (response.headers &&
                (response.headers['content-type'] ||
                    response.headers['Content-Type'])) ||
            'application/json; charset=utf-8';
        const forwardedHeaders = [
            'x-sonos-response-source',
            'x-sonos-response-stale',
            'x-sonos-observed-at',
            'x-sonos-age-ms',
        ];

        forwardedHeaders.forEach(headerName => {
            const headerValue =
                response.headers &&
                (response.headers[headerName] ||
                    response.headers[headerName.toLowerCase()]);
            if (headerValue) {
                res.setHeader(headerName, headerValue);
            }
        });

        res.type(contentType)
            .status(response.statusCode)
            .send(response.body);
    } catch (err) {
        const statusCode = Number(err && err.statusCode) || 502;
        console.error(
            `Sonos API error for ${route}:`,
            (err && err.message) || err
        );
        res.status(statusCode).json({
            error: (err && err.message) || 'Sonos API request failed',
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
        const response = await rpn({
            method,
            uri: url,
            body,
            json: true,
            resolveWithFullResponse: true,
            simple: false,
        });

        res.status(response.statusCode).json(response.body);
    } catch (err) {
        const statusCode = Number(err && err.statusCode) || 502;
        console.error(
            `Sonos API error for ${method} ${route}:`,
            (err && err.message) || err
        );
        res.status(statusCode).json({
            error: (err && err.message) || 'Sonos API request failed',
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
