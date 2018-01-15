var log = console.log;

class App {
  constructor(args) {
    this.window = args.window;
    this.$ = args.container;
    this.grid = args.grid;
    this.config = args.config;
    this.rooms = args.config.rooms;
    this.secret = args.secret;
    this.listeners = [];
  }

  submit(event) {
    event.app = this;
    this.listeners.forEach(l => l.onMessage(event));
  }

  subscribe(listener) {
    this.listeners.push(listener);
  }

  emojiWithName(name) {
    return this.config.emojis[name];
  }

  // This is the one method called from main.js
  run() {
    this.grid.init($(this.window), this);

    // TODO: instead perioically send messages
    this.config.poll.forEach(p => {
      var f = () => this.onAction(p.action, p.args)
      setInterval(f, p.period);
    });

    // this.listen('Cell.Click', (e) => {
    //   var b = e.Cell.data('config');
    //   if(b && b.onPress) {
    //     this.onAction(b.onPress.action, b.onPress.args)
    //   }
    // });
    //
    // this.listen('Cell.DoubleClick', (e) => {
    //   var d = e.Cell.data('config');
    //   if(d && d.onDoublePress) {
    //     this.onAction(d.onDoublePress.action, d.onDoublePress.args);
    //   }
    // });

    // // move to Cell class
    // this.listen('Room.Changed', (e) => {
    //   this.grid.allCells().forEach(c => {
    //     var d = c.data('config');
    //     if(d && d.activeWhenRoom) {
    //       if (e.ToRoom == d.activeWhenRoom) {
    //         c.addClass('active');
    //       } else {
    //         c.removeClass('active');
    //       }
    //     }
    //   })
    // });

    // this.listen('Room.Changed', (e) => {
    //   this.getState();
    // });
    //
    // this.listen('App.Started', (e) => {
    //   this.changeRoom('Kitchen');
    // })
    //
    // this.listen('App.Started', (e) => {
    //   this.reindex();
    // });
    //
    // this.submit('App.Started', {});
    this.changeRoom('Kitchen');
  }

  // allJoin(room) {
  //   // TODO: could be more clever about getting all room names from `/zones`
  //   // it's in .members.roomName
  //   log('allJoin ' + room)
  //   var delay = 0;
  //   this.config.rooms.filter( x => x != room ).forEach( other => {
  //     setTimeout(() => this.request('http://retropie.local:5005/' + other + '/join/' + room), delay)
  //     delay += 1000; // only 1 request/second
  //   });
  // }

  // reindex() {
  //   this.request('http://retropie.local:5005/reindex')
  // }
  //
  // refresh() {
  //   window.location.reload();
  // }

  setBanner(msg) {
    this.$.find('.state-Music').html(msg ? msg.substr(0,19) : '');
  }
  setBackgroundImage(url) {
    if(url) {
      $('body').css({backgroundImage: 'url("' + url + '")'});
    }
    else {
      $('body').css({backgroundImage: ''});
    }
  }

  changeRoom(toRoom) {
    var oldRoom = this.room;
    this.room = toRoom;
    this.submit({
      Name:     'Room.Changed',
      FromRoom: oldRoom,
      ToRoom:   toRoom
    });
  }

  request(url) {
    if(window.location.href.match(/.*debug.*/)) {
      alert('fake request '+url);
      return {};
    }
    return $.ajax(url)
      .fail(err  => console.log(url, err));
  }

  getState() {
    $.ajax(
      'http://retropie.local:5005/' + this.room + '/state'
    ).done(resp => {
      this.submit({
        Name: 'Room.StateObserved',
        State: resp,
      });
    });
  }

  onAction(action, params) {

    switch(action) {
    case 'AllJoin':
      this.allJoin.apply(this, params);
      break;
    case 'ChangeRoom':
      this.changeRoom.apply(this, params);
      break;
    case 'Music.GetState':
      this.getState();
      break;
    case 'Lights.On':
        this.request('http://maker.ifttt.com/trigger/' + this.room + '_scene_bright/with/key/' + this.secret.ifttt.key);
        this.request('http://maker.ifttt.com/trigger/' + this.room + '_switch_on/with/key/' + this.secret.ifttt.key);
        // this.request('http://retropie:5005/' + this.room + '/say/on/en-gb')
        break;
    case 'Lights.Scene.Dim':
        this.request('http://maker.ifttt.com/trigger/' + this.room + '_scene_dim/with/key/' + this.secret.ifttt.key);
        this.request('http://maker.ifttt.com/trigger/' + this.room + '_switch_off/with/key/' + this.secret.ifttt.key);
        // this.request('http://retropie:5005/' + this.room + '/say/dimmed/en-gb')
        break;
    case 'Lights.Off':
        this.request('http://maker.ifttt.com/trigger/' + this.room + '_off/with/key/' + this.secret.ifttt.key);
        this.request('http://maker.ifttt.com/trigger/' + this.room + '_switch_off/with/key/' + this.secret.ifttt.key);
        // this.request('http://retropie:5005/' + this.room + '/say/off/en-gb')
        break;
    case 'Lights.Scene.Savana':
        this.request('http://maker.ifttt.com/trigger/' + this.room + '_scene_savanna/with/key/' + this.secret.ifttt.key);
        this.request('http://maker.ifttt.com/trigger/' + this.room + '_switch_off/with/key/' + this.secret.ifttt.key);
        // this.request('http://retropie:5005/' + this.room + '/say/savanna/en-gb')
        break;
    case 'Music.PlayPause':
        this.request(
          'http://retropie.local:5005/' + this.room + '/playpause'
        )
        break;
    case 'Music.Preset':
      this.request(
        'http://retropie.local:5005/' + this.room + '/preset/' + params[0]
      );
      break;
    case 'Music.VolumeUp':
      this.request(
        'http://retropie.local:5005/' + this.room + '/volume/+5'
      )
      break;
    case 'Music.VolumeDown':
      this.request(
        'http://retropie.local:5005/' + this.room + '/volume/-5'
      );
      break;
    case 'Music.Next':
      this.request(
        'http://retropie.local:5005/' + this.room + '/next'
      );
      break;
    case 'App.Refresh':
      this.refresh();
      break;
    }
  }
}
