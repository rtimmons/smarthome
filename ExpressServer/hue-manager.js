const hue = require("node-hue-api");
const secret = require('./secret.js');

// --------------------------
// Using a promise
hue.nupnpSearch().then((r) => console.log(JSON.dump(r))).done();


class HueManager {
  constructor() {
    
  }
}

module.exports = HueManager;
