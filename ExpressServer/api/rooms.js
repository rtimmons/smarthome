const Promise = require('promise');
const rq = Promise.denodeify(require('request'));
const request = require('request');

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

function stateResponse(state, zones) {
  const derived = {};
  derived.musicSource = 'stationName' in state.currentTrack ? 'Pandora' : 'Other';
  derived.zoneMembers = [].concat(...zones.map(z => z.members)).map(m => ({
    volume: m.state.volume,
    roomName: m.roomName,
  })).filter(o => o.roomName !== state.roomName);
  return { derived, state, zones };
}

const sonos = new Sonos('http://smarterhome.local:5005');

app.get('/rooms/:room/state.json', async (areq, ares) => {
  const { room } = areq.params;
  const state = await sonos.get(room, 'state');
  const zones = await sonos.get(room, 'zones');
  const resp = stateResponse(state, zones);
  ares.send(resp);
});

// passthru raw sonos requests
app.get(/sonos\/(.+)$/, async (areq, ares) => {
  areq.pipe(request(sonos.url(areq.params[0]))).pipe(ares);
});

app.listen(3005, () => console.log('Running'));
