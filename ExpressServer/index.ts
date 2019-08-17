// Simple API for things that are hard or can't be implemented
// within the font-end.

import * as bodyParser from 'body-parser';
import * as cors from 'cors';
import * as express from 'express';
import * as MyPromise from 'promise';
import * as request from 'request';
import {Cache as MyCache} from './cache';

// name can't be much longer; matches with stop in package.json
process.title = 'smhexprsrv';

const requestDenoded = MyPromise.denodeify(require('request'));


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
const host = req => req.headers.host.replace(/:\d+$/, '');

const cache = new MyCache();

const sonosUrl = 'http://smarterhome.local:5005';

// //////////////////////////////////////////////////////////////////
// configs

const redirs = {
  // 1 is up
  '1up': req => `http://${req.headers.host}/up`,
  '1down': req => `http://${req.headers.host}/down`,
  '1left': () => `${sonosUrl}/Bedroom/favorite/Play%20NPR%20One`,
  '1right': () => `${sonosUrl}/Bedroom/favorite/Zero%207%20Radio`,
  // 2 is right
  '2right': () => `${sonosUrl}/Bedroom/next`,
};

const sonosPipe = function(route, req, res) {
  const url = `${sonosUrl}/${route}`;
  console.log(`Requesting ${url}`);
  return req.pipe(request(url)).pipe(res);
};

const sonosGet = function(route) {
  return (req, res) => {
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

app.get('/sonos/:rest', (req, res) => {
  return sonosPipe(req.params.rest, req, res);
});

app.get('/b/:to', (req, res) => {
  const url = redirs[req.params.to](req, res);
  console.log(`/b/${req.params.to} => ${url}`);
  req.pipe(request(url)).pipe(res);
});

// make all rooms in same zone as :room have volume == min volume of any room in the zone
app.get('/same/:room', (areq, ares) => {
  ares.set('Content-Type', 'application/json');
  requestDenoded(`${sonosUrl}/${areq.params.room}/zones`)
    .then((res) => {
      try {
        // *should* be easy to make this apply to all zones, but currently
        // have no use for it.
        const zone = JSON.parse(res.body)[0];
        const volumes = zone.members.map(m => ({ roomName: m.roomName, volume: m.state.volume }));
        const min = Math.min.apply(null, volumes.map(v => v.volume));
        const others = volumes.filter(v => v.volume !== min);
        if (others.length === 0) {
          return MyPromise.resolve();
        }
        return MyPromise.all.apply(null,
          others.map(o => requestDenoded(`${sonosUrl}/${o.roomName}/volume/${min}`)));
      } catch (e) {
        console.log(e);
        return MyPromise.reject(e);
      }
    })
    .then(() => MyPromise.resolve({ status: 'success' }))
    .then(res => ares.send(res))
    .catch((err) => {
      console.error(err);
      ares.end();
    });
});

app.get('/down', (areq, ares) => {
  ares.set('Content-Type', 'application/json');
  requestDenoded(`${sonosUrl}/Bedroom/state`)
    .then((res) => {
      const j = JSON.parse(res.body);
      return MyPromise.resolve({ volume: j.volume, playbackState: j.playbackState });
    })
    .then((state) => {
      const url = sonosUrl + (
        (state.playbackState === 'PLAYING' && state.volume <= 3)
          ? '/Bedroom/pause' : '/Bedroom/groupVolume/-1');
      console.log(url);
      return requestDenoded(url);
    })
    .then(res => ares.send(res.body))
    .then(() => ares.end())
    .catch((err) => {
      console.error(err);
    });
});

// probably refactor /up and /down; they're copy/pasta
app.get('/up', (areq, ares) => {
  ares.set('Content-Type', 'application/json');
  requestDenoded(`${sonosUrl}/Bedroom/state`)
    .then((res) => {
      const j = JSON.parse(res.body);
      return MyPromise.resolve({ volume: j.volume, playbackState: j.playbackState });
    })
    .then((state) => {
      const url = sonosUrl + (
        (state.playbackState === 'PAUSED_PLAYBACK')
          ? '/Bedroom/play' : '/Bedroom/groupVolume/+1');
      console.log(url);
      return requestDenoded(url);
    })
    .then(res => ares.send(res.body))
    .catch((err) => {
      console.error(err);
    });
});

app.post('/report', (req, res) => {
  console.log('REPORT', req.body);
  res.send('OK');
});

app.get('/journal', (req, res) => {
  res.redirect(301, `http://${host(req)}:19531/browse`);
});


app.get('/temp', (areq, ares) => {
  ares.set('Content-Type', 'text/plain');
  ares.write('');
  ares.end();
});

app.get('/temp-broken', (areq, ares) => {
  const url = 'http://grovepi.local/GrovePi/cgi-bin/temp.py';
  ares.set('Content-Type', 'text/plain');
  return cache
    .get('temp', requestDenoded(url))
    .then(res => MyPromise.resolve(res.body.trim()))
    .then((res) => {
      const i = parseInt(res, 10);
      return MyPromise.resolve(Number.isNaN(i) ? 0 : i);
    })
    .catch((err) => {
      console.log('Error fetching temp', err);
      return MyPromise.resolve(0);
    })
    .then((temp) => {
      ares.write(temp);
      ares.end();
    });
});

app.get('/', (req, res) => {
  res.set('Content-Type', 'application/json');
  res.send('{}');
});

// ///////////////////////////////////////////////////////////////////
// actually run the thing

app.listen(3000, () => console.log('Listening on port 3000!'));
