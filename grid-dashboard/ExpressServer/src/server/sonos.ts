import { Request as RQ, Response as RS, Router } from 'express';
import * as rpn from 'request-promise-native';

import '../types/sonos';

import { appConfig } from './config';

const app = Router();

const sonosPipe = (route: string, req: RQ, res: RS): RS => {
    const url = `${appConfig.sonosUrl}/${route}`;
    return req.pipe(rpn(url)).pipe(res);
};

const sonosGet = (route: string): ((req: RQ, res: RS) => RS) => {
    return (req: RQ, res: RS) => {
        return sonosPipe(route, req, res);
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
        return sonosPipe(`sonos/${rest}`, req, res);
    });
})();

// Custom routes /same/:room, /down, /up are now handled by sonos-api add-on
// Simple proxy routes below forward to sonos-api which has the business logic
app.get('/same/:room', (req: RQ, res: RS) => {
    return sonosPipe(`same/${req.params.room}`, req, res);
});
app.get('/down', (req: RQ, res: RS) => {
    return sonosPipe('down', req, res);
});
app.get('/up', (req: RQ, res: RS) => {
    return sonosPipe('up', req, res);
});

export const sonos = app;
