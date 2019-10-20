// Simple API for things that are hard or can't be implemented
// within the font-end.

import * as bodyParser from 'body-parser';
import * as cors from 'cors';
import * as express from 'express';
// tslint:disable-next-line:no-duplicate-imports
import { Request as RQ, Response as RS } from 'express';
import * as morgan from 'morgan';
import * as path from 'path';
import * as rpn from 'request-promise-native';
import * as serveFavicon from 'serve-favicon';

import '../types/sonos';

// name can't be much longer; matches with stop in package.json
process.title = 'smhexprsrv';

// /////////////////////////////////////////////////////////////////
// build app

const app = express();

// support json encoded bodies
app.use(bodyParser.json());

// support encoded bodies
app.use(bodyParser.urlencoded({ extended: true }));

app.use(cors());

app.use(serveFavicon(path.join(__dirname, '..', 'public', 'favicon.ico')));

app.use('/ui', express.static('src/public'));

app.use(morgan('tiny'));

// /////////////////////////////////////////////////////////////////
// helpers

// removes port
const host = (req: RQ) => {
    const header = req.headers.host;
    if (header === undefined) {
        return;
    }
    req.headers.host = header.replace(/:\d+$/, '');
};

const sonosUrl = 'http://smarterhome.local:5005';

// //////////////////////////////////////////////////////////////////
// configs

const redirs: { [key: string]: (req: RQ, res: RS) => string } = {
    // 1 is up
    '1up': (req: RQ) => `http://${req.headers.host}/up`,
    '1down': (req: RQ) => `http://${req.headers.host}/down`,
    '1left': () => `${sonosUrl}/Bedroom/favorite/Play%20NPR%20One`,
    '1right': () => `${sonosUrl}/Bedroom/favorite/Zero%207%20Radio`,
    // 2 is right
    '2right': () => `${sonosUrl}/Bedroom/next`,
};

const sonosPipe = (route: string, req: RQ, res: RS): RS => {
    const url = `${sonosUrl}/${route}`;
    return req.pipe(rpn(url)).pipe(res);
};

const sonosGet = (route: string): ((req: RQ, res: RS) => RS) => {
    return (req: RQ, res: RS) => {
        return sonosPipe(route, req, res);
    };
};

// //////////////////////////////////////////////////////////////
// routes

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

app.get('/b/:to', (req: RQ, res: RS) => {
    const url = redirs[req.params['to']](req, res);
    console.log(`/b/${req.params['to']} => ${url}`);
    req.pipe(rpn(url)).pipe(res);
});

// make all rooms in same zone as :room have volume == min volume of any room in the zone
app.get(
    '/same/:room',
    wrap(async (areq: RQ, ares: RS) => {
        const room = areq.params['room'];
        const res = await rpn.get(`${sonosUrl}/${room}/zones`);
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
        const min = Math.min.apply(null, volumes.map(v => v.volume));
        const others = volumes.filter(v => v.volume !== min);
        await Promise.all(
            others.map(async o => {
                await rpn.get(`${sonosUrl}/${o.roomName}/volume/${min}`);
            })
        );
    })
);

app.get(
    '/down',
    wrap(async (areq: RQ, ares: RS) => {
        const res = await rpn.get(`${sonosUrl}/Bedroom/state`);
        const j = JSON.parse(res.body as string);
        const url =
            sonosUrl +
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
        const res = await rpn.get(`${sonosUrl}/Bedroom/state`);
        const j = JSON.parse(res.body as string);
        const url =
            sonosUrl +
            (j.playbackState === 'PAUSED_PLAYBACK'
                ? '/Bedroom/play'
                : '/Bedroom/groupVolume/+1');
        const thenState = await rpn.get(url);
        ares.send(thenState.body);
    })
);

app.post('/report', (req: RQ, res: RS) => {
    console.log('REPORT', req.body);
    res.send('OK');
});

app.get('/journal', (req: RQ, res: RS) => {
    res.redirect(301, `http://${host(req)}:19531/browse`);
});

app.get('/', (req: RQ, res: RS) => {
    res.set('Content-Type', 'application/json');
    res.send('{}');
});

// ///////////////////////////////////////////////////////////////////
// actually run the thing

app.listen(3000, () => console.log('Listening on port 3000!'));
