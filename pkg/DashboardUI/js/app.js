var log = console.log;

class App {
  constructor(args) {
    this.window = args.window;
    this.$ = args.container;
    this.grid = args.grid;
    this.config = args.config;
  }

  run() {
    this.grid.init($(this.window));
    this.config.cells.forEach(b => {
      this.grid.assign(
        {y: b.y, x: b.x, w: b.w},
        this.config.emojis[b.icon], 
        b.claz, b.activeWhenRoom,
        () => this.onAction(b.onPress.action, b.onPress.args),
      );
    });
    this.config.poll.forEach(p => {
      setInterval(() => this.onAction(p.action, p.args), p.period);
    });

    this.changeRoom('Kitchen');
  }

  changeRoom(toRoom) {
    this.$.find('.whenRoom').removeClass('active');
    this.room = toRoom;
    console.log(this.$.find('.whenRoom' + '.room-' + toRoom).addClass('active'));
    log('Switched to room', this.room);
  }

  listen(toRoom) {
    this.request('http://retropie.local:5005/' + this.room + '/join/' + toRoom);
  }

  request(url) {
    return $.ajax(url)
      .fail(err  => console.log(url, err));
  }

  getState() {
    $.ajax(
      'http://retropie.local:5005/' + this.room + '/state'
    ).done(resp => {
      var title = resp.currentTrack.title;
      this.$.find('.state-Music').html(title.substr(0,21));
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
    if(this.mode == 'Listen' && action == 'ChangeRoom') {
      this.listen(this.room, params[0]);
      delete this.mode;
    }
    switch(action) {
    case 'Music.StartListen':
      this.mode = 'Listen';
      break;

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
