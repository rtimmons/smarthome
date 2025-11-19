import { Request as RQ, Response as RS, Router } from 'express';
import * as rpn from 'request-promise-native';

import '../types/sonos';

import { appConfig } from './config';

const app = Router();

const sonosPipe = (route: string, req: RQ, res: RS): void => {
    const url = `${appConfig.sonosUrl}/${route}`;
    req.pipe(rpn(url))
        .on('error', (err: any) => {
            console.error(`Sonos API error for ${route}:`, err.message);
            if (!res.headersSent) {
                res.status(err.statusCode || 500).json({
                    error: err.message || 'Sonos API request failed',
                    route: route
                });
            }
        })
        .pipe(res);
};

const sonosGet = (route: string): ((req: RQ, res: RS) => void) => {
    return (req: RQ, res: RS) => {
        sonosPipe(route, req, res);
    };
};

app.get('/pause', sonosGet('pause'));
app.get('/play', sonosGet('play'));
app.get('/tv', sonosGet('preset/all-tv'));
app.get('/07', sonosGet('favorite/Zero 7 Radio'));
app.get('/quiet', sonosGet('groupVolume/7'));

(() => {
    const rex: RegExp = /sonos\/(.*)$/;
    app.get(rex, (req: RQ, res: RS) => {
        const match = req.path.match(rex);
        if (match === null) {
            throw new Error(`Invalid sonos request ${req.path}`);
        }
        const rest = match[1];
        // Forward to sonos-api with /sonos/ prefix
        sonosPipe(`sonos/${rest}`, req, res);
    });
})();

// Custom routes /same/:room, /down, /up are now handled by sonos-api add-on
// Simple proxy routes below forward to sonos-api which has the business logic
app.get('/same/:room', (req: RQ, res: RS) => {
    sonosPipe(`same/${req.params.room}`, req, res);
});
app.get('/down', (req: RQ, res: RS) => {
    sonosPipe('down', req, res);
});
app.get('/up', (req: RQ, res: RS) => {
    sonosPipe('up', req, res);
});

export const sonos = app;
