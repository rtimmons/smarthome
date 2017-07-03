var log = console.log;

class App {
  constructor($elt) {
    this.$ = $elt;
    this.changeRoom('Kitchen');
  }

  changeRoom(toRoom) {
    this.$.find('.room-' + this.room).removeClass('active');
    this.room = toRoom;
    this.$.find('.room-' + this.room).addClass('active');
    log('Switched to room', this.room);
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
      // TODO: bring back display state
      this.$.find('#state-Music').html(title);
    });
  }

  cell(row, col) {
    return this.$.find('#cell-'+row+'-'+col);
  }

  assign(row, col, emoji, action, args) {
    args = args || [];
    this.cell(row,col).html(emoji).click(() => this.onAction(action, args));
  }

  configure(conf) {
    conf.cells.forEach(b => {
      this.assign(b.y, b.x, conf.emojis[b.icon], b.onPress.action, b.onPress.args)
    });
  }

    // TODO: support these actions?
    // 'ChangeRoom',
    //
    // 'Music.Join',
    // 'Music.VolumeUp',
    // 'Music.VolumeDown',
    // 'Music.Mute',
    //
    // 'Music.Resume',
    // 'Music.Pause',
    // 'Music.Skip',
    // 'Music.ThumbsUp',
    // 'Music.ThumbsDown',
    //
    // 'Music.PlayX', (params with what to play)
    //
    // 'Light.On',
    // 'Light.Dim',
    // 'Light.Off',
    // 'Light.Scene',  (params with what to play)

  onAction(action, params) {
    log('Action', action, params);
    switch(action) {
    case 'ChangeRoom':
      this.changeRoom.apply(this, params);
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
  }
}
