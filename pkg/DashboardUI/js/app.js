class App {
  constructor(url, $elt) {
    this.url = url;
    this.$ = $elt;
  }

  run() {
    this.init();
  }

  request(url) {
    return $.ajax()
  }

  onPress($elt) {
    var action = $elt.attr('action');
    switch(action) {
    case 'Music.VolumeUp':
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
