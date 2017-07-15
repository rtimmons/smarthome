var log = console.log;

class App {
  constructor(args) {
    this.window = args.window;
    this.$ = args.container;
    this.grid = args.grid;
    this.config = args.config;
    this.listeners = {};
  }

  submit(topic, event) {
    (this.listeners[topic] || []).forEach(l => l(event));
  }

  listen(topic, callback) {
    this.listeners[topic] = this.listeners[topic] || [];
    this.listeners[topic].push(callback);
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

    this.listen('Room.StateObserved', (e) => {
      var track = e.State.currentTrack;
      var artUrl = track.albumArtUri;
      if(artUrl) {
        $('body').css({backgroundImage: 'url("' + artUrl + '")'});
      }
      else {
        $('body').css({backgroundImage: ''});
      }
    })
  }

  changeRoom(toRoom) {
    this.$.find('.whenRoom').removeClass('active');
    this.room = toRoom;
    log('Switched to room', this.room);
  }

  request(url) {
    return $.ajax(url)
      .fail(err  => console.log(url, err));
  }

  getState() {
    $.ajax(
      'http://retropie.local:5005/' + this.room + '/state'
    ).done(resp => {
      this.submit('Room.StateObserved', {
        State: resp,
      });
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
      log(this.room + ' joins ' + params[0]);
      this.request('http://retropie.local:5005/' + this.room + '/join/' + params[0]);
      delete this.mode;
      return;
    }

    if(this.mode == 'Broadcast' && action == 'ChangeRoom') {
      log(this.room + ' broadcasts to ' + params[0]);
      this.request('http://retropie.local:5005/' + params[0] + '/join/' + this.room);
      delete this.mode;
      return;
    }

    switch(action) {
    case 'Music.StartListen':
      this.mode = 'Listen';
      break;
    case 'Music.StartBroadcast':
      this.mode = 'Broadcast';
      break;

    case 'ChangeRoom':
      this.changeRoom.apply(this, params);
      break;
    case 'Music.GetState':
      this.getState();
      break;
    case 'Lights.On':
        this.request('http://maker.ifttt.com/trigger/' + this.room + '_scene_bright/with/key/cLNpbWpb3jYP550-Mna27W');
        this.request('http://maker.ifttt.com/trigger/' + this.room + '_switch_on/with/key/cLNpbWpb3jYP550-Mna27W');
        this.request('http://retropie:5005/' + this.room + '/say/on/en-gb')
        break;
    case 'Lights.Scene.Dim':
        this.request('http://maker.ifttt.com/trigger/' + this.room + '_scene_dim/with/key/cLNpbWpb3jYP550-Mna27W');
        this.request('http://maker.ifttt.com/trigger/' + this.room + '_switch_off/with/key/cLNpbWpb3jYP550-Mna27W');
        this.request('http://retropie:5005/' + this.room + '/say/dimmed/en-gb')
        break;
    case 'Lights.Off':
        this.request('http://maker.ifttt.com/trigger/' + this.room + '_off/with/key/cLNpbWpb3jYP550-Mna27W');
        this.request('http://maker.ifttt.com/trigger/' + this.room + '_switch_off/with/key/cLNpbWpb3jYP550-Mna27W');
        this.request('http://retropie:5005/' + this.room + '/say/off/en-gb')
        break;
    case 'Lights.Scene.Savana':
        this.request('http://maker.ifttt.com/trigger/' + this.room + '_scene_savanna/with/key/cLNpbWpb3jYP550-Mna27W');
        this.request('http://maker.ifttt.com/trigger/' + this.room + '_switch_off/with/key/cLNpbWpb3jYP550-Mna27W');
        this.request('http://retropie:5005/' + this.room + '/say/savanna/en-gb')
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
