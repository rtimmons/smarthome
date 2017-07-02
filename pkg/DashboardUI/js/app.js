var log = console.log;

class App {
  constructor(url, $elt) {
    this.url = url;
    this.$ = $elt;
    this.room = 'Kitchen'; // TODO pass in config and use DefaultRoom
    log('Initialized for room', this.room);
  }

  run() {
    this.init();
  }

  request(url) {
    return $.ajax(url).then(resp => console.log(resp));
  }

  onPress($elt) {
    var action = $elt.attr('action');
    switch(action) {
    case 'Music.VolumeUp':
      // TODO: use this.room or some indirection
      this.request('http://retropie:5005/Kitchen/volume/+5')
    }

    var old = $elt.clone(true);
    $elt.html('🤔');
    setTimeout(() => $elt.replaceWith(old),1000);    
  }

  init() {
    var appThis = this;
    this.$.find('*[action]').click(function(evt){
      appThis.onPress($(this));
      evt.preventDefault();
      return true;
    });
  }
}
