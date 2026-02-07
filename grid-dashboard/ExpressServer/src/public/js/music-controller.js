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
        // Build URL using current page's base path for ingress compatibility
        var path = args.join('/');
        if (!this.root) {
            // Get base path from current location, removing ALL trailing slashes
            var basePath = window.location.pathname.replace(/\/+$/, ''); // Remove all trailing slashes
            var url = basePath + '/' + path;
        } else {
            var url = [this.root].concat(args).join('/');
        }

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

    parseJsonMaybe(value) {
        if (typeof value !== 'string') {
            return value;
        }
        try {
            return JSON.parse(value);
        } catch (err) {
            console.log('Failed to parse Sonos response as JSON', err);
            return null;
        }
    }

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
            var parsed = this.parseJsonMaybe(resp);
            if (!parsed) {
                return;
            }
            this.pubsub.submit('Room.StateObserved', {
                State: parsed,
            });
        });

        this.request('sonos', 'zones').done(resp => {
            var parsed = this.parseJsonMaybe(resp);
            if (!parsed) {
                return;
            }
            this.pubsub.submit('Room.ZonesObserved', {
                Zones: parsed,
            });
        });
    }
}
