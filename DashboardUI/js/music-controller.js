class MusicController {
  constructor(args) {
    this.requester = args.requester;
    this.root = args.root;
    this.app = args.app;
    this.pubsub = args.pubsub;
  }

  request() {
    var args = Array.prototype.slice.call(arguments);
    const currRoom = this.app.currentRoom();
    const replaceName = n => n.replace(/\$room/g, currRoom);
    args = args.map(a => replaceName(a));
    args = [this.root].concat(args);
    var url = args.join('/');

    return this.requester.request(url);
  }

  pause()       { this.request('$room', 'pause'       ); }
  playPause()   { this.request('$room', 'playpause'   ); }
  preset(name)  { this.request('$room', 'preset', name); }
  volumeUp()    { this.request('$room', 'groupVolume','+2' ); }
  volumeDown()  { this.request('$room', 'groupVolume', '-2'); }
  next()        { this.request('$room', 'next'        ); }
  favorite(name){ this.request('$room', 'favorite', name); }
  volumeSame()  { this.request('same', '$room'); }

  leaveRoom(r)  { this.request(r, 'leave');   }
  joinRoom(a,b) { this.request(a, 'join', b); }

  onMessage(e) {}

  allJoin(room) {
    let delay = 0;
    this.app.config.rooms.filter( x => x != room ).forEach( other => {
      setTimeout(() => this.request([other, 'join', '$room']), delay);
      delay += 250; // only 1 request/quarter-second
    });
  }

  fetchState() {
    this.request('$room', 'state').done(resp => {
      this.pubsub.submit('Room.StateObserved', {
        State: resp,
      });
    });

    this.request('zones').done(resp => {
      this.pubsub.submit('Room.ZonesObserved', {
        Zones: resp,
      })
    });
  }

}
