const secret = require('./secret.js').secret.hue;

const hueAll = require("node-hue-api");
const HueApi = hueAll.HueApi;
const lightState = hueAll.lightState;


// TODO: better strategy for these
const APP_DESCRIPTION = 'SmartHomeDashboard';
const HOST = '192.168.1.238';

const display = function(r) {
  console.log(JSON.stringify(r));
};

// hue.nupnpSearch().then((r) => {
//   console.log(r[0].ipaddress);
//   console.log(JSON.stringify(r));
// }).done()

const state = lightState.create();

class HueManager {
  constructor() {
    this.username = secret.username;
  }
  _ensureRegistered() {
    if (typeof this.username === 'undefined') {
      return new HueApi().registerUser(HOST, APP_DESCRIPTION)
        .then(r => {
          this.username = r;
          this.hue = new HueApi(HOST, this.username);
        });
    } else {
      this.hue = new HueApi(HOST, this.username);
    }
    return Promise.resolve();
  }
  on() {
    return this._ensureRegistered().then(() => {
      return this.hue.setLightState(1, state.on());
    });
  }
  off() {
    return this._ensureRegistered().then(() => {
      return this.hue.setLightState(1, state.off());
    });
  }
}

module.exports = HueManager;
