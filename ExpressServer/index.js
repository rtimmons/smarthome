;process.title = "smhexprsrv" // name can't be much longer; matches with stop in package.json

var express = require('express');
var request = require('request');

var app = express();

var redirs = {
  '1up':    'http://smarterhome.local:5005/Bedroom/volume/+2',
  '1down':  'http://smarterhome.local:5005/Bedroom/volume/-2',
  '1left':  'http://smarterhome.local:5005/Bedroom/favorite/Play%20NPR%20One',
  '1right': 'http://smarterhome.local:5005/Bedroom/favorite/Zero%207%20Radio',
};

app.get('/b/:to', function(req, res){
  var url = redirs[req.params.to];
  console.log(url);
  req.pipe(request(url)).pipe(res);
});

app.get('/', function(req, res){
  res.send(JSON.stringify(redirs));
});

app.listen(3000, () => console.log('Listening on port 3000!'));
