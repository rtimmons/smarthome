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
      var cell = this.grid.cell({y: b.y, x: b.x, w: b.w});
      cell.html(this.config.emojis[b.icon]);
      cell.click(() => this.onAction(b.onPress.action, b.onPress.args));
      cell.addClass(b.claz);
      cell.data('config', b);
    });

    this.config.poll.forEach(p => {
      var f = () => this.onAction(p.action, p.args)
      setInterval(f, p.period);
    });

    this.listen('Room.StateObserved', (e) => {
      var track = e.State.currentTrack;
      var artUrl = track.albumArtUri;
      if(artUrl) {
        $('body').css({backgroundImage: 'url("' + artUrl + '")'});
      }
      else {
        $('body').css({backgroundImage: ''});
      }
      var title = track.title;
      this.$.find('.state-Music').html(title ? title.substr(0,21) : '');
    });

    this.listen('Room.Changed', (e) => {
      var cells = this.grid.allCells();
      cells.forEach(c => {
        var d = c.data('config');
        if(d && d.activeWhenRoom) {
          if (e.ToRoom == d.activeWhenRoom) {
            c.addClass('active');
          } else {
            c.removeClass('active');
          }
        }
      })
    });
    this.listen('Room.Changed', (e) => {
      this.getState();
    });

    this.listen('App.Started', (e) => {
      this.changeRoom('Kitchen');
    })

    this.submit('App.Started', {});
  }

  changeRoom(toRoom) {
    var oldRoom = this.room;
    this.room = toRoom;
    this.submit('Room.Changed', {FromRoom: oldRoom, ToRoom: toRoom})
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
    case 'Lights.SceneX':
      this.request('http://maker.ifttt.com/trigger/kitchen_switch_on/with/key/cLNpbWpb3jYP550-Mna27W');
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
