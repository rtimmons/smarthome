;process.title = "smhexprsrv" // name can't be much longer; matches with stop in package.json

var express = require('express');
var app = express();

var redirs = {
  '/npr':   'http://smarterhome.local:5005/Bedroom/favorite/Play%20NPR%20One',
  '/zero':  'http://smarterhome.local:5005/Bedroom/favorite/Zero%207%20Radio',
  '/up':    'http://smarterhome.local:5005/Bedroom/volume/+1',
  '/down':  'http://smarterhome.local:5005/Bedroom/volume/-1'
};

for(var path in redirs) {
  var dest = redirs[path];
  app.get(path, function(req, res) {
    res.redirect(301, dest);
  });
}

app.get('/', function(req, res){
  res.send(JSON.stringify(redirs));
});

app.listen(3000, () => console.log('Listening on port 3000!'));
