class MusicController {
  constructor(args) {
    this.requester = args.requester;
    this.root = args.root;
    this.app = args.app;
  }

  request() {
    var args = Array.prototype.slice.call(arguments);
    args = args.map(a => a == '$room' ? this.app.currentRoom() : a);
    args = [this.root].concat(args);
    var url = args.join('/');

    return this.requester.request(url);
  }

  playPause()   { this.request('$room', 'playpause'   ); }
  preset(name)  { this.request('$room', 'preset', name); }
  volumeUp()    { this.request('$room', 'volume','+5' ); }
  volumeDown()  { this.request('$room', 'volume', '-5'); }
  next()        { this.request('$room', 'next'        ); }
  favorite(name){ this.request('$room', 'favorite', name); }

  leaveRoom(r)  { this.request(r, 'leave');   }
  joinRoom(a,b) { this.request(a, 'join', b); }

  onMessage(e) {
  }

  allJoin(room) {
    var delay = 0;
    this.app.config.rooms.filter( x => x != room ).forEach( other => {
      setTimeout(() => this.requester.request('http://' +  + window.location.host + ':5005/' + other + '/join/' + room), delay)
      delay += 1000; // only 1 request/second
    });
  }

  fetchState() {
    this.request('state').done(resp => {
      this.app.submit({
        Name: 'Room.StateObserved',
        State: resp,
      });
    });

    this.request('zones').done(resp => {
      this.app.submit({
        Name: 'Room.ZonesObserved',
        Zones: resp,
      })
    });
  }

}
