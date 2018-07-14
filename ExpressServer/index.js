;process.title = "smhexprsrv" // name can't be much longer; matches with stop in package.json

var express = require('express');
var request = require('request');
var cors = require('cors')

const NodeCache = require( "node-cache" );

const cache = new NodeCache({ stdTTL: 60, checkperiod: 120 });
var app = express();

// https://scotch.io/tutorials/use-expressjs-to-get-url-and-post-parameters
var bodyParser = require('body-parser');
app.use(bodyParser.json()); // support json encoded bodies
app.use(bodyParser.urlencoded({ extended: true })); // support encoded bodies

app.use(cors());

////////////////////////////////////////////////////////////////////

var redirs = {
  '1up':    'http://smarterhome.local:5005/Bedroom/groupVolume/+1',
  '1down':  'http://smarterhome.local:5005/Bedroom/groupVolume/-1',
  '1left':  'http://smarterhome.local:5005/Bedroom/favorite/Play%20NPR%20One',
  '1right': 'http://smarterhome.local:5005/Bedroom/favorite/Zero%207%20Radio',
};

var pretty = `<html><body><pre>${JSON.stringify(redirs, null, 2)}</pre></body></html>`;

////////////////////////////////////////////////////////////////

app.get('/b/:to', function(req, res){
  var url = redirs[req.params.to];
  req.pipe(request(url)).pipe(res);
});

app.post('/report', function(req, res){
  console.log('REPORT', req.body);
  res.send('OK');
});

app.get('/journal', function(req, res){
  var host = req.headers.host.replace(/:\d+$/,''); // remove port
  res.redirect(301, `http://${host}:19531/browse`);
});

app.get('/temp', function(areq, ares){
  var url = "http://grovepi.local/GrovePi/cgi-bin/temp.py";
  var temp = cache.get( "temp" ); // way to do this as .get(k, () => 7) => 7 if not found?
  ares.set('Content-Type', "text/plain");
  if ( temp == undefined ){
    request(url, (err, res, body) => {
      if (err) {
        console.log("Error fetching temp", err);
        cache.set("temp", "0");
        ares.write("0");
        ares.end();
        return;
      }
      body = body.trim();
      console.log("Refreshing temp value to ", body);
      cache.set("temp", body);
      ares.write(body);
      ares.end();
      return;
    });
  } else {
    ares.write(temp);
    ares.end();
  }
})

app.get('/', function(req, res){
  res.send(pretty);
});

/////////////////////////////////////////////////////////////////////

app.listen(3000, () => console.log('Listening on port 3000!'));
