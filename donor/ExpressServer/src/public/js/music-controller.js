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

    pause() {
        this.request('sonos', '$room', 'pause');
    }
    playPause() {
        this.request('sonos', '$room', 'playpause');
    }
    preset(name) {
        this.request('sonos', '$room', 'preset', name);
    }
    volumeUp() {
        this.request('sonos', '$room', 'groupVolume', '+2');
    }
    volumeDown() {
        this.request('sonos', '$room', 'groupVolume', '-2');
    }
    setVolume(vol) {
        this.request('sonos', '$room', 'groupVolume', new String(vol));
    }
    next() {
        this.request('sonos', '$room', 'next');
    }
    favorite(name) {
        this.request('sonos', '$room', 'favorite', name);
    }
    volumeSame() {
        // not provided by sonos natively
        this.request('same', '$room');
    }

    leaveRoom(r) {
        this.request('sonos', r, 'leave');
    }
    joinRoom(a, b) {
        this.request('sonos', a, 'join', b);
    }

    onMessage(e) {}

    allJoin(room) {
        let delay = 0;
        this.app.config.rooms
            .filter(x => x != room)
            .forEach(other => {
                setTimeout(() => this.request('sonos', other, 'join', '$room'), delay);
                delay += 250; // only 1 request/quarter-second
            });
    }

    fetchState() {
        this.request('sonos', '$room', 'state').done(resp => {
            this.pubsub.submit('Room.StateObserved', {
                State: resp,
            });
        });

        this.request('sonos', 'zones').done(resp => {
            this.pubsub.submit('Room.ZonesObserved', {
                Zones: resp,
            });
        });
    }
}
