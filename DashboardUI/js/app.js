var log = console.log;

class App {
  constructor(args) {
    this.window    = args.window;
    this.$         = args.container;
    this.grid      = args.grid;
    this.config    = args.config;
    this.rooms     = args.config.rooms;
    this.secret    = args.secret;
    this.pubsub    = args.pubsub;

    // TODO: move to object-factory
    this.musicController = new MusicController({
      requester: this,
      root: 'http://' + this.secret.host.hostname + ':5005',
      app: this,
      pubsub: this.pubsub,
    });

    // TODO: move to pubsub class
    this.pubsub.subscribe('*', {onMessage: e => {
      this.eachCell(c => c.onMessage(e));
      this.musicController.onMessage(e);
    }});
  }

  // TODO: move to config class
  emojiWithName(name) {
    return this.config.emojis[name];
  }

  // TODO: move to grid view
  eachCell(f) {
    return this.grid.allCells().map(c => f(c));
  }

  // This is the one method called from main.js
  run() {
    this.grid.init($(this.window), this);

    this.pubsub.setGlobal('App', this);
    this.pubsub.submit('App.Initialized', {});

    // TODO: instead perioically send messages
    // TODO: move to config class
    this.config.poll.forEach(p => {
      var f = () => this.onAction(p.action, p.args)
      setInterval(f, p.period);
    });
  }

  // TODO: move to gridview?
  setBanner(msg) {
    if (msg == this.banner) {
      return;
    }
    var banner = this.$.find('.state-Music div');
    if (msg.length >= 19) {
      banner.addClass('scroll');
    }
    else {
      banner.removeClass('scroll');
    }
    banner.html(msg);
    this.banner = msg;
  }

  // TODO: move to gridview?
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
    this.pubsub.submit('Room.Changed', {
      FromRoom: oldRoom,
      ToRoom:   toRoom
    });
  }

  // TODO: move to request class?
  request(url) {
    return $.ajax(url)
      .fail(err  => console.error(url, err));
  }

  // TODO: don't call directly/ expose musicController?
  fetchState() {
    this.musicController.fetchState();
  }

  // TODO: move to action listeners
  onAction(action, params, evt) {
    switch(action) {

    // TODO: BrowserController
    case 'App.Refresh':
      console.log('Reloading');
      this.window.location.reload(true);
      break;
    
    // TODO: is this used?
    case 'AllJoin':
      this.musicController.allJoin(params[0]);
      break;

    case 'ChangeRoom':
      this.changeRoom.apply(this, params);
      break;

    // TODO: lights controller?
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

    // TODO: grid can listen for this
    case 'GetValues':
      this.grid.getValues();
      break;

    // TODO: move to Music.* listeners to MusicController
    case 'Music.ToggleRoom':
        if (evt.Event.Cell.isActive()) {
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
    case 'Music.Pause':
        this.musicController.pause();
        break;
    case 'Music.Favorite':
      this.musicController.favorite(params[0]);
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
