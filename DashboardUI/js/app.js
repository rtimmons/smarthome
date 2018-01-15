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

    this.musicController = new MusicController({
      requester: this,
      root: 'http://retropie.local:5005',
      app: this,
    });
  }

  submit(event) {
    event.app = this;
    this.listeners.forEach(l => {
      setTimeout(() => l.onMessage(event), 0);
    });
  }

  subscribe(listener) {
    this.listeners.push(listener);
  }

  emojiWithName(name) {
    return this.config.emojis[name];
  }

  eachCell(f) {
    return this.grid.allCells().map(c => f(c));
  }

  // This is the one method called from main.js
  run() {
    this.grid.init($(this.window), this);

    // TODO: instead perioically send messages
    this.config.poll.forEach(p => {
      var f = () => this.onAction(p.action, p.args)
      setInterval(f, p.period);
    });

    this.changeRoom('Kitchen');
  }

  setBanner(msg) {
    if (msg == this.banner) {
      return;
    }
    this.$.find('.state-Music').html(msg ? msg.substr(0,19) : '');
    this.banner = msg;
  }
  setBackgroundImage(url) {
    if (url == this.backgroundImage) {
      return;
    }
    if(url) {
      $('body').css({backgroundImage: 'url("' + url + '")'});
    }
    else {
      $('body').css({backgroundImage: ''});
    }
    this.backgroundImage = url;
  }

  /**
   * zones is like
   * [ {members: [list string room names]} ]
   */
  updateZones(zones) {
    var sameZone = zones.filter(z => z.members.indexOf(this.room) >= 0)[0].members;
    var arg = {
      on: sameZone,
      off: this.rooms.filter(r => sameZone.indexOf(r) < 0),
    };
    this.grid.updateZones(arg);
  }

  currentRoom() {
    return this.room;
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
    return $.ajax(url)
      .fail(err  => console.log(url, err));
  }

  fetchState() {
    this.musicController.fetchState();
  }

  onAction(action, params, evt) {
    switch(action) {
    case 'AllJoin':
      this.musicController.allJoin(params[0]);
      break;
    case 'ChangeRoom':
      this.changeRoom.apply(this, params);
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

    case 'Music.ToggleRoom':
        if (evt.Cell.isActive()) {
          this.musicController.leaveRoom(params[0]);
        }
        else {
          this.musicController.joinRoom(params[0], this.room);
        }
        break;
    case 'Music.FetchState':
        this.fetchState();
        break;
    case 'Music.PlayPause':
        this.musicController.playPause();
        break;
    case 'Music.Preset':
      this.musicController.preset(params[0]);
      break;
    case 'Music.VolumeUp':
      this.musicController.volumeUp();
      break;
    case 'Music.VolumeDown':
      this.musicController.volumeDown();
      break;
    case 'Music.Next':
      this.musicController.next();
      break;

    consle.error('Unknown action ' + action);
    }
  }
}
