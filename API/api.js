var hue = require("node-hue-api");

// https://github.com/peter-murray/node-hue-api#installation

const API_CONFIG = {
  // make undefined to look it up
  ip: '192.168.1.16',
  // secret? idk.
  user: 'wAdDo9PF3j79jG1aOUc6aTebqziyGCCN9tPkckSD',
  description: 'SmartHomeDashboard',
};

const light_config = {
  
};

var displayResult = function(result) {
    console.log(JSON.stringify(result, null, 2));
};

// var resolveIP = API_CONFIG.ip ?
//   () => Promise.resolve([{ipaddress: API_CONFIG.ip}])
// : hue.nupnpSearch;
//
// var resolveUser = API_CONFIG.user ?
//   (ip) => Promise.resolve(API_CONFIG.user)
// : (ip) => hueApi.registerUser(ip, API_CONFIG.description);
//
// var createApi = (username) => Promise.resolve(hue.HueApi(ip,username));
//
// resolveIP()
// .then((bridges) => {
//   var ip = bridges[0].ipaddress;
//   return Promise.resolve(ip);
// })
// .then(resolveUser)
// .then((user) => {
//   return
// });

var api = new hue.HueApi(API_CONFIG.ip, API_CONFIG.user);
api.lights().then(displayResult).done();
