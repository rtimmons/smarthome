// Simple API for things that are hard or can't be implemented
// within the font-end.

// name can't be much longer; matches with stop in package.json
;process.title = "smhexprsrv" 

///////////////////////////////////////////////////////////////////
// Requires

const bodyParser     = require('body-parser');
const cors           = require('cors')
const express        = require('express');
const Promise        = require('promise');
const request        = require('request');
const requestDenoded = Promise.denodeify(require('request'));

const Cache          = require('./cache.js');

///////////////////////////////////////////////////////////////////
// build app

var app = express();

// support json encoded bodies
app.use(bodyParser.json());

// support encoded bodies
app.use(bodyParser.urlencoded({ extended: true }));

app.use(cors());

///////////////////////////////////////////////////////////////////
// helpers

// removes port
const host = (req) => req.headers.host.replace(/:\d+$/,'');

var cache = new Cache();

////////////////////////////////////////////////////////////////////
// configs

var redirs = {
  // 1 is up
  '1up':    'http://smarterhome.local:5005/Bedroom/groupVolume/+1',
  '1down':  'http://smarterhome.local:5005/Bedroom/groupVolume/-1',
  '1left':  'http://smarterhome.local:5005/Bedroom/favorite/Play%20NPR%20One',
  '1right': 'http://smarterhome.local:5005/Bedroom/favorite/Zero%207%20Radio',
  // 2 is right
  '2right': 'http://smarterhome.local:5005/Bedroom/next',
};

var pretty = `<html><body><pre>${JSON.stringify(redirs, null, 2)}</pre></body></html>`;

////////////////////////////////////////////////////////////////
// routes

app.get('/b/:to', function(req, res){
  var url = redirs[req.params.to];
  req.pipe(request(url)).pipe(res);
});


app.get('/down', function(areq, ares){
  ares.set('Content-Type', "application/json");
  requestDenoded('http://smarterhome.local:5005/state')
    .then(res => {
      var j = JSON.parse(res.body);
      return Promise.resolve({volume: j.volume, playbackState: j.playbackState});
    })
    .then(state => {
      var url = `http://${host(areq)}:5005/` + (
        (state.playbackState == 'PLAYING' && state.volume <= 2) ?
          'pause' : 'groupVolume/-1');
      console.log(url);
      return requestDenoded(url);
    })
    .then(res => ares.send(res.body))
    .catch(err => {
      console.error(error);
    });
});

// probably refactor /up and /down; they're copy/pasta
app.get('/up', function(areq, ares){
  ares.set('Content-Type', "application/json");
  requestDenoded('http://smarterhome.local:5005/state')
    .then(res => {
      var j = JSON.parse(res.body);
      return Promise.resolve({volume: j.volume, playbackState: j.playbackState});
    })
    .then(state => {
      var url = `http://${host(areq)}:5005/` + (
        (state.playbackState == 'PAUSED_PLAYBACK') ?
          'play' : 'groupVolume/+1');
      console.log(url);
      return requestDenoded(url);
    })
    .then(res => ares.send(res.body))
    .catch(err => {
      console.error(error);
    });
});

app.post('/report', function(req, res){
  console.log('REPORT', req.body);
  res.send('OK');
});

app.get('/journal', function(req, res){
  res.redirect(301, `http://${host(req)}:19531/browse`);
});


app.get('/temp', function(areq, ares){
  var url = "http://grovepi.local/GrovePi/cgi-bin/temp.py";
  ares.set('Content-Type', "text/plain");
  return cache
  .get('temp', requestDenoded(url))
  .then(res => Promise.resolve(res.body.trim()))
  .then(res => {
    var i = parseInt(res);
    return Promise.resolve(Number.isNaN(i) ? 0 : i);
  })
  .catch(err => {
    console.log("Error fetching temp", err);
    return Promise.resolve(0);
  })
  .then(temp => {
    ares.write(temp);
    ares.end();
  });
})

app.get('/', function(req, res){
  res.send(pretty);
});

/////////////////////////////////////////////////////////////////////
// actually run the thing

app.listen(3000, () => console.log('Listening on port 3000!'));
