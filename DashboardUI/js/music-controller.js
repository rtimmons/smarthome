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
