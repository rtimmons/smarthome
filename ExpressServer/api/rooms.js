const Promise = require('promise');
const rq = Promise.denodeify(require('request'));
const request = require('request');
const clone = require('clone');

const app = require('express')();

class Sonos {
  constructor(root) {
    this.root = root;
  }

  url(...args) {
    return [this.root].concat(args).join('/');
  }

  async get(...args) {
    const url = this.url(...args);
    console.log('requesting ', url);
    const raw = await rq(url);
    return JSON.parse(raw.body);
  }
}

function asRooms(room, zones) {
  return [].concat(...zones
    .map((zone, zoneIndex) => zone.members.map((member) => {
      const out = clone(member);
      out.state.musicSource = 'stationName' in out.state.currentTrack ? 'Pandora' : 'Other';
      out.zoneIndex = zoneIndex;
      return out;
    })));
}

const sonos = new Sonos('http://smarterhome.local:5005');

app.get('/rooms/:room/state.json', async (areq, ares) => {
  const { room } = areq.params;
  const zones = await sonos.get('zones');
  const rooms = asRooms(room, zones);
  const ownRoom = rooms.filter(r => r.roomName === room)[0];
  const others = rooms.filter(r => r.roomName !== room);
  ares.send({ state: ownRoom, others });
});

// app.get('/rooms/:room/alljoin', async (areq, ares) => {
//   const { room } = areq.params;
//   const state = await sonos.get(room, 'state');
//   const zones = await sonos.get(room, 'zones');
//   const resp = stateResponse(state, zones);
//   ares.send(resp);
// });

// passthru raw sonos requests
app.get(/sonos\/(.+)$/, async (areq, ares) => {
  const url = sonos.url(areq.params[0]);
  console.log(url);
  areq.pipe(request(url)).pipe(ares);
});

app.listen(3005, () => console.log('Running'));
