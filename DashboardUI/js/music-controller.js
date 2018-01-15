class MusicController {
  constructor(args) {
    this.requester = args.requester;
    this.root = args.root;
    this.app = args.app;
  }

  _url(args) {
    var parts = [this.root, this.app.currentRoom()].concat(args);
    return parts.join('/');
  }
  _noroom(args) {
    args = Array.prototype.slice.call(arguments);
    var parts = [this.root].concat(args);
    return parts.join('/');
  }

  request() {
    var args = Array.prototype.slice.call(arguments);
    return this.requester.request(
      this._url(args)
    );
  }

  playPause()   { this.request('playpause'); }
  preset(name)  { this.request('preset', name); }
  volumeUp()    { this.request('volume','+5'); }
  volumeDown()  { this.request('volume', '-5'); }
  next()        { this.request('next'); }

  allJoin(room) {
    // TODO: could be more clever about getting all room names from `/zones`
    // it's in .members.roomName
    log('allJoin ' + room)
    var delay = 0;
    this.app.config.rooms.filter( x => x != room ).forEach( other => {
      setTimeout(() => this.requester.request('http://retropie.local:5005/' + other + '/join/' + room), delay)
      delay += 1000; // only 1 request/second
    });
  }

  // /Kitchen/join/Office This will join the Kitchen player to the group that Office currently belong to.
  joinRoom(a,b) {
    console.log('joinRoom', a, b);
    var url = this._noroom(a, 'join', b);
    console.log(url);
    this.requester.request(url);
  }

  leaveRoom(room) {
    this.request('leave');
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
