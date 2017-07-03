var log = console.log;

class App {
  constructor(url, $elt) {
    this.url = url;
    this.$ = $elt;
    this.changeRoom('Kitchen');
  }

  changeRoom(toRoom) {
    this.$.find('.room-' + this.room).removeClass('active');
    this.room = toRoom;
    this.$.find('.room-' + this.room).addClass('active');
    log('Switched to room', this.room);
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

  getState() {
    $.ajax(
      'http://retropie.local:5005/' + this.room + '/state'
    ).done(resp => {
      var title = resp.currentTrack.title;
      this.$.find('#state-Music').html(title);
    });
  }

  onPress($elt) {
    var action = $elt.attr('action');
    log('Action', action);
    switch(action) {
    case 'ChangeRoom':
      this.changeRoom($elt.attr('toRoom'));
      break;
    case 'Music.GetState':
      this.getState();
      break;
    case 'Music.VolumeUp':
      this.request(
        'http://retropie.local:5005/' + this.room + '/volume/+5'
      )
      break;
    case 'Music.VolumeDown':
      this.request(
        'http://retropie.local:5005/' + this.room + '/volume/-5'
      )
    }

    // var old = $elt.clone(true);
    // $elt.html('🤔');
    // setTimeout(() => $elt.replaceWith(old),1000);
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
