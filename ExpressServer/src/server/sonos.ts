import {Request as RQ, Response as RS, Router} from "express";
import * as rpn from "request-promise-native";

import '../types/sonos';

import {appConfig} from './config';

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
        return sonosPipe(rest, req, res);
    });
})();

const wrap = <T>(
    fn: (req: RQ, res: RS) => T
): ((req: RQ, res: RS) => Promise<T | undefined>) => {
    return async (areq: RQ, ares: RS) => {
        try {
            ares.set('Content-Type', 'application/json');
            return await fn(areq, ares);
        } catch (e) {
            console.log(e);
            ares.status(500);
            ares.json({ error: e.toString() });
            return undefined;
        } finally {
            ares.end();
        }
    };
};


// make all rooms in same zone as :room have volume same as active room
app.get(
    '/same/:room',
    wrap(async (areq: RQ, ares: RS) => {
        const room = areq.params['room'];
        const res = await rpn.get(`${appConfig.sonosUrl}/${room}/zones`);
        const zones: Sonos.Zone[] = JSON.parse(res);
        // For some reason /:room/zones gives back status of
        // all zones not just the one of the :room parameter.
        const zone: Sonos.Zone = zones.filter(
            zone => zone.members.map(m => m.roomName).indexOf(room) >= 0
        )[0];
        const volumes = zone.members.map(m => ({
            roomName: m.roomName,
            volume: m.state.volume,
        }));
        const myVolume = volumes.find(r => r.roomName === room)!.volume;
        const others = volumes.filter(v => v.volume !== myVolume);
        await Promise.all(
            others.map(async o => {
                await rpn.get(`${appConfig.sonosUrl}/${o.roomName}/volume/${myVolume}`);
            })
        );
        ares.status(200);
        ares.json({status: 'success'});
    })
);

app.get(
    '/down',
    wrap(async (areq: RQ, ares: RS) => {
        const res = await rpn.get(`${appConfig.sonosUrl}/Bedroom/state`);
        const j = JSON.parse(res.body as string);
        const url =
            appConfig.sonosUrl +
            (j.playbackState === 'PLAYING' && j.volume <= 3
                ? '/Bedroom/pause'
                : '/Bedroom/groupVolume/-1');
        const thenState = await rpn.get(url);
        ares.send(thenState.body);
    })
);

// probably refactor /up and /down; they're copy/pasta
app.get(
    '/up',
    wrap(async (areq: RQ, ares: RS) => {
        const res = await rpn.get(`${appConfig.sonosUrl}/Bedroom/state`);
        const j = JSON.parse(res.body as string);
        const url =
            appConfig.sonosUrl +
            (j.playbackState === 'PAUSED_PLAYBACK'
                ? '/Bedroom/play'
                : '/Bedroom/groupVolume/+1');
        const thenState = await rpn.get(url);
        ares.send(thenState.body);
    })
);

export const sonos = app;

