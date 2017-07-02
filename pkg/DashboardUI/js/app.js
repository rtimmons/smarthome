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
    log('Request ', url);
    return $.ajax(url)
      .done(resp => console.log(url, resp))
      .fail(err  => console.log(url, err));
  }

  onPress($elt) {
    var action = $elt.attr('action');
    log('Action', action);
    switch(action) {
    case 'Music.VolumeUp':
      // TODO: use this.room or some indirection
      this.request('http://retropie.local:5005/Kitchen/volume/+5')
      break;
    case 'Music.VolumeDown':
      // TODO: use this.room or some indirection
      this.request('http://retropie.local:5005/Kitchen/volume/-5')
      break;
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
