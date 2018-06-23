;process.title = "smhexprsrv" // name can't be much longer; matches with stop in package.json

var express = require('express');
var request = require('request');
var cors = require('cors')

var app = express();

// https://scotch.io/tutorials/use-expressjs-to-get-url-and-post-parameters
var bodyParser = require('body-parser');
app.use(bodyParser.json()); // support json encoded bodies
app.use(bodyParser.urlencoded({ extended: true })); // support encoded bodies

app.use(cors());

////////////////////////////////////////////////////////////////////

var redirs = {
  '1up':    'http://smarterhome.local:5005/Bedroom/volume/+2',
  '1down':  'http://smarterhome.local:5005/Bedroom/volume/-2',
  '1left':  'http://smarterhome.local:5005/Bedroom/favorite/Play%20NPR%20One',
  '1right': 'http://smarterhome.local:5005/Bedroom/favorite/Zero%207%20Radio',
};

var pretty = `<html><body><pre>${JSON.stringify(redirs, null, 2)}</pre></body></html>`;

////////////////////////////////////////////////////////////////

app.get('/b/:to', function(req, res){
  var url = redirs[req.params.to];
  console.log(url);
  req.pipe(request(url)).pipe(res);
});

app.post('/report', function(req, res){
  console.log('REPORT', req.body);
  res.send('OK');
});

app.get('/temp', function(req, res){
  var temp = Math.floor(Math.random() * 30) + 90
  res.status(200).send(new String(temp));
})

app.get('/', function(req, res){
  res.send(pretty);
});

/////////////////////////////////////////////////////////////////////

app.listen(3000, () => console.log('Listening on port 3000!'));
