// Simple API for things that are hard or can't be implemented
// within the font-end.

import * as bodyParser from 'body-parser';
import * as cors from 'cors';
import * as express from 'express';
import * as rpn from 'request-promise-native';

import "./types/sonos";

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

// /////////////////////////////////////////////////////////////////
// helpers

// removes port
const host = (req: express.Request) => {
  const header = req.headers.host;
  if (header === undefined) { return; }
  req.headers.host = header.replace(/:\d+$/, '');
};

const sonosUrl = 'http://smarterhome.local:5005';

// //////////////////////////////////////////////////////////////////
// configs

const redirs: {[key: string]: (req: express.Request, res: express.Response) => string} = {
  // 1 is up
  '1up': (req: express.Request) => `http://${req.headers.host}/up`,
  '1down': (req: express.Request) => `http://${req.headers.host}/down`,
  '1left': () => `${sonosUrl}/Bedroom/favorite/Play%20NPR%20One`,
  '1right': () => `${sonosUrl}/Bedroom/favorite/Zero%207%20Radio`,
  // 2 is right
  '2right': () => `${sonosUrl}/Bedroom/next`,
};

const sonosPipe = function(route: string, req: express.Request, res: express.Response): express.Response {
  const url = `${sonosUrl}/${route}`;
  console.log(`Requesting ${url}`);
  return req.pipe(rpn(url)).pipe(res);
};

const sonosGet = function(route: string): (req: express.Request, res: express.Response) => express.Response {
  return (req: express.Request, res: express.Response) => {
    return sonosPipe(route, req, res);
  };
};

// //////////////////////////////////////////////////////////////
// routes

app.get('/pause', sonosGet('pause'));
app.get('/play',  sonosGet('play'));
app.get('/tv',    sonosGet('preset/all-tv'));
app.get('/07',    sonosGet('favorite/Zero 7 Radio'));
app.get('/quiet', sonosGet('groupVolume/7'));

app.get('/sonos/:rest', (req: express.Request, res: express.Response) => {
  return sonosPipe(req.params['rest'], req, res);
});

const wrap = function<T>(fn: (req: express.Request, res: express.Response) => T):
    (req: express.Request, res: express.Response) => Promise<T|undefined> {
  return async function(areq: express.Request, ares: express.Response) {
    try {
      ares.set('Content-Type', 'application/json');
      return await fn(areq, ares);
    } catch(e) {
      console.log(e);
      ares.status(500);
      ares.json({error: e.toString()});
      return undefined;
    } finally {
      ares.end();
    }
  };
};

app.get('/b/:to', (req: express.Request, res: express.Response) => {
  const url = redirs[req.params['to']](req, res);
  console.log(`/b/${req.params['to']} => ${url}`);
  req.pipe(rpn(url)).pipe(res);
});

// make all rooms in same zone as :room have volume == min volume of any room in the zone
app.get('/same/:room', wrap(async (areq: express.Request, ares: express.Response) => {
  const room = areq.params['room'];
  const res = await rpn.get(`${sonosUrl}/${room}/zones`);
  const zones: Sonos.Zone[] = JSON.parse(res);
  // For some reason /:room/zones gives back status of
  // all zones not just the one of the :room parameter.
  const zone: Sonos.Zone = zones.filter(zone =>
      zone.members.map(m => m.roomName).indexOf(room) >= 0)[0];
  const volumes = zone.members.map(m => ({ roomName: m.roomName, volume: m.state.volume }));
  const min = Math.min.apply(null, volumes.map(v => v.volume));
  const others = volumes.filter(v => v.volume !== min);
  await Promise.all(others.map(async (o) => {
    await rpn.get(`${sonosUrl}/${o.roomName}/volume/${min}`);
  }));
}));

app.get('/down', wrap(async (areq: express.Request, ares: express.Response) => {
  const res = await rpn.get(`${sonosUrl}/Bedroom/state`);
  const j = JSON.parse(res.body as string);
  const url = sonosUrl + (
      (j.playbackState === 'PLAYING' && j.volume <= 3)
          ? '/Bedroom/pause' : '/Bedroom/groupVolume/-1');
  const thenState = await rpn.get(url);
  ares.send(thenState.body);
}));

// probably refactor /up and /down; they're copy/pasta
app.get('/up', wrap(async (areq: express.Request, ares: express.Response) => {
    const res = await rpn.get(`${sonosUrl}/Bedroom/state`);
    const j = JSON.parse(res.body as string);
    const url = sonosUrl + (
        (j.playbackState === 'PAUSED_PLAYBACK')
            ? '/Bedroom/play' : '/Bedroom/groupVolume/+1');
    const thenState = await rpn.get(url);
    ares.send(thenState.body);
}));

app.post('/report', (req: express.Request, res: express.Response) => {
  console.log('REPORT', req.body);
  res.send('OK');
});

app.get('/journal', (req: express.Request, res: express.Response) => {
  res.redirect(301, `http://${host(req)}:19531/browse`);
});

app.get('/', (req: express.Request, res: express.Response) => {
  res.set('Content-Type', 'application/json');
  res.send('{}');
});

// ///////////////////////////////////////////////////////////////////
// actually run the thing

app.listen(3000, () => console.log('Listening on port 3000!'));
