var log = console.log;

class App {
  constructor(args) {
    this.window = args.window;
    this.$ = args.container;
    this.grid = args.grid;
    this.config = args.config;
    this.rooms = args.config.rooms;
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
      var cell = this.grid.cell(b);
      cell.data('config', b);
      cell.html(this.config.emojis[b.icon]);
      cell.addClass(b.claz);

      var tapped = false;
      var app = this;
      // hacky thing to bind double-tap
      cell.on("touchstart",function(e){
        if(!tapped){
          tapped=setTimeout(function(){
            tapped=null;
            cell.click();
          },300);
        } else {
          clearTimeout(tapped);
          tapped=null;
          cell.dblclick();
        }
        e.preventDefault();
      });

      cell.click(() => this.submit('Cell.Click', {Cell: cell}));
      cell.dblclick(() => this.submit('Cell.Dblclick', {Cell: cell}));
      cell.on('doubletap', () => this.submit('Cell.Dblclick', {Cell: cell}));
    });

    this.config.poll.forEach(p => {
      var f = () => this.onAction(p.action, p.args)
      setInterval(f, p.period);
    });

    this.listen('Cell.Click', (e) => {
      var b = e.Cell.data('config');
      if(b && b.onPress) {
        this.onAction(b.onPress.action, b.onPress.args)
      }
    });

    this.listen('Cell.Dblclick', (e) => {
      var d = e.Cell.data('config');
      if(d && d.onDblPress) {
        this.onAction(d.onDblPress.action, d.onDblPress.args);
      }
    });

    this.listen('Room.StateObserved', (e) => {
      var track = e.State.currentTrack;
      var artUrl = track.absoluteAlbumArtUri || track.albumArtUri;
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
      this.grid.allCells().forEach(c => {
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

    this.listen('App.Started', (e) => {
      this.reindex();
    });

    this.submit('App.Started', {});
  }

  allJoin(room) {
    // TODO: could be more clever about getting all room names from `/zones`
    // it's in .members.roomName
    log('allJoin ' + room)
    var delay = 0;
    this.config.rooms.filter( x => x != room ).forEach( other => {
      setTimeout(() => this.request('http://retropie.local:5005/' + other + '/join/' + room), delay)
      delay += 1000; // only 1 request/second
    });
  }

  reindex() {
    this.request('http://retropie.local:5005/reindex')
  }

  refresh() {
    window.location.reload();
  }

  changeRoom(toRoom) {
    var oldRoom = this.room;
    this.room = toRoom;
    this.submit('Room.Changed', {FromRoom: oldRoom, ToRoom: toRoom})
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
      this.submit('Room.StateObserved', {
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
        this.request('http://maker.ifttt.com/trigger/' + this.room + '_scene_bright/with/key/cLNpbWpb3jYP550-Mna27W');
        this.request('http://maker.ifttt.com/trigger/' + this.room + '_switch_on/with/key/cLNpbWpb3jYP550-Mna27W');
        // this.request('http://retropie:5005/' + this.room + '/say/on/en-gb')
        break;
    case 'Lights.Scene.Dim':
        this.request('http://maker.ifttt.com/trigger/' + this.room + '_scene_dim/with/key/cLNpbWpb3jYP550-Mna27W');
        this.request('http://maker.ifttt.com/trigger/' + this.room + '_switch_off/with/key/cLNpbWpb3jYP550-Mna27W');
        // this.request('http://retropie:5005/' + this.room + '/say/dimmed/en-gb')
        break;
    case 'Lights.Off':
        this.request('http://maker.ifttt.com/trigger/' + this.room + '_off/with/key/cLNpbWpb3jYP550-Mna27W');
        this.request('http://maker.ifttt.com/trigger/' + this.room + '_switch_off/with/key/cLNpbWpb3jYP550-Mna27W');
        // this.request('http://retropie:5005/' + this.room + '/say/off/en-gb')
        break;
    case 'Lights.Scene.Savana':
        this.request('http://maker.ifttt.com/trigger/' + this.room + '_scene_savanna/with/key/cLNpbWpb3jYP550-Mna27W');
        this.request('http://maker.ifttt.com/trigger/' + this.room + '_switch_off/with/key/cLNpbWpb3jYP550-Mna27W');
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
