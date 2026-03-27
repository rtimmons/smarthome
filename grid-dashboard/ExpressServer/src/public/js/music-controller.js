class MusicController {
    constructor(args) {
        this.requester = args.requester;
        this.root = args.root;
        this.app = args.app;
        this.pubsub = args.pubsub;
    }

    resolveUrl(path) {
        if (!this.root) {
            var basePath = window.location.pathname.replace(/\/+$/, '');
            return basePath + '/' + path;
        }

        return [this.root, path].join('/');
    }

    request() {
        var args = Array.prototype.slice.call(arguments);
        var currRoom = this.app.currentRoom();
        var replaceName = function(n) {
            return n.replace(/\$room/g, currRoom);
        };
        args = args.map(a => replaceName(a));
        var path = args.join('/');
        return this.requester.request(this.resolveUrl(path));
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
        this.pubsub.submit('Room.ZonesObserved', {
            Zones: null,
            Meta: { unknown: true },
        });
        this.request('sonos', r, 'leave');
    }
    joinRoom(a, b) {
        this.pubsub.submit('Room.ZonesObserved', {
            Zones: null,
            Meta: { unknown: true },
        });
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

    responseMeta(xhr) {
        if (!xhr || typeof xhr.getResponseHeader !== 'function') {
            return {};
        }

        var ageMs = Number(xhr.getResponseHeader('X-Sonos-Age-Ms'));
        return {
            source: xhr.getResponseHeader('X-Sonos-Response-Source') || 'live',
            stale:
                (xhr.getResponseHeader('X-Sonos-Response-Stale') || '')
                    .toLowerCase() === 'true',
            observedAt: xhr.getResponseHeader('X-Sonos-Observed-At') || '',
            ageMs: Number.isFinite(ageMs) ? ageMs : 0,
        };
    }

    allJoin(room) {
        var payload = {
            targetRoom: room,
            roomNames: this.app.config.rooms.slice(),
            requestedFromRoom: this.app.currentRoom(),
        };

        this.requester.request({
            url: this.resolveUrl('sonos-intents/group-all'),
            method: 'POST',
            contentType: 'application/json',
            dataType: 'json',
            data: JSON.stringify(payload),
        }).done(resp => {
            var parsed = this.parseJsonMaybe(resp);
            if (!parsed || !parsed.intent || parsed.intent.status !== 'running') {
                return;
            }

            this.pubsub.submit('Intent.StateObserved', {
                Status: {
                    activeIntent: parsed.intent,
                    recentIntent: null,
                    serverTime: new Date().toISOString(),
                },
            });
        });
    }

    fetchState() {
        this.request('sonos', '$room', 'state').done((resp, _textStatus, xhr) => {
            var parsed = this.parseJsonMaybe(resp);
            if (!parsed) {
                return;
            }
            this.pubsub.submit('Room.StateObserved', {
                State: parsed,
                Meta: this.responseMeta(xhr),
            });
        });

        this.request('sonos', 'zones').done((resp, _textStatus, xhr) => {
            var parsed = this.parseJsonMaybe(resp);
            if (!parsed) {
                return;
            }
            this.pubsub.submit('Room.ZonesObserved', {
                Zones: parsed,
                Meta: this.responseMeta(xhr),
            });
        }).fail(xhr => {
            this.pubsub.submit('Room.ZonesObserved', {
                Zones: null,
                Meta: {
                    unknown: true,
                    statusCode: (xhr && xhr.status) || 0,
                },
            });
        });

        this.request('sonos-intents', 'status').done(resp => {
            var parsed = this.parseJsonMaybe(resp);
            if (!parsed) {
                return;
            }
            this.pubsub.submit('Intent.StateObserved', {
                Status: parsed,
            });
        });
    }
}
