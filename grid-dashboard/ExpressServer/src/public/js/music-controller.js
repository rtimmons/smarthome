class MusicController {
    constructor(args) {
        this.requester = args.requester;
        this.root = args.root;
        this.app = args.app;
        this.pubsub = args.pubsub;
        this.stateRequestSequence = 0;
        this.zonesRequestSequence = 0;
        this.statusRequestSequence = 0;
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
        args = args.map(function(value) {
            return encodeURIComponent(replaceName(String(value)));
        });
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
        var operationGeneration = arguments.length > 1 ? arguments[1] : null;
        var request = this.request('sonos', '$room', 'preset', name);
        this.observeTopologyRequest(
            request,
            operationGeneration,
            null,
            true
        );
        return request;
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
        var operationGeneration = arguments.length > 1 ? arguments[1] : null;
        var request = this.request('sonos', r, 'leave');
        this.observeTopologyRequest(request, operationGeneration, r);
        return request;
    }
    joinRoom(a, b) {
        var operationGeneration = arguments.length > 2 ? arguments[2] : null;
        var request = this.request('sonos', a, 'join', b);
        this.observeTopologyRequest(request, operationGeneration, a);
        return request;
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
        var source = xhr.getResponseHeader('X-Sonos-Response-Source') || 'live';
        var unavailableRooms = xhr.getResponseHeader('X-Sonos-Unavailable-Rooms') || '';
        return {
            source: source,
            unknown:
                source.toLowerCase() === 'unknown' ||
                (xhr.getResponseHeader('X-Sonos-Response-Unknown') || '')
                    .toLowerCase() === 'true',
            stale:
                (xhr.getResponseHeader('X-Sonos-Response-Stale') || '')
                    .toLowerCase() === 'true',
            observedAt: xhr.getResponseHeader('X-Sonos-Observed-At') || '',
            ageMs: Number.isFinite(ageMs) ? ageMs : 0,
            unavailableRooms: unavailableRooms.split(',').filter(Boolean),
        };
    }

    failureMessage(xhr) {
        if (xhr && xhr.responseJSON && xhr.responseJSON.error) {
            return xhr.responseJSON.error;
        }
        return 'Sonos grouping request failed';
    }

    observeTopologyRequest(
        request,
        operationGeneration,
        roomName,
        publishStatus
    ) {
        if (operationGeneration === null || operationGeneration === undefined) {
            return request;
        }

        request.done(resp => {
            var parsed = this.parseJsonMaybe(resp);
            var operation = this.app.acceptTopologyOperation(
                operationGeneration,
                parsed,
                roomName
            );
            if (publishStatus && operation) {
                var terminal = operation.status !== 'queued' &&
                    operation.status !== 'running';
                this.app.updateIntentStatus({
                    activeIntent: terminal ? null : operation,
                    recentIntent: terminal ? operation : null,
                    serverTime: new Date().toISOString(),
                });
            }
        }).fail(xhr => {
            this.app.failTopologyOperation(
                operationGeneration,
                this.failureMessage(xhr),
                roomName
            );
        });
        return request;
    }

    allJoin(room, operationGeneration) {
        var payload = {
            targetRoom: room,
            roomNames: this.app.config.rooms.slice(),
            requestedFromRoom: this.app.currentRoom(),
        };

        var request = this.requester.request({
            url: this.resolveUrl('sonos-intents/group-all'),
            method: 'POST',
            contentType: 'application/json',
            dataType: 'json',
            data: JSON.stringify(payload),
        });
        request.done(resp => {
            var parsed = this.parseJsonMaybe(resp);
            var operation = this.app.acceptTopologyOperation(
                operationGeneration,
                parsed,
                null
            );
            if (!operation) {
                return;
            }

            this.app.updateIntentStatus({
                activeIntent: operation,
                recentIntent: null,
                serverTime: new Date().toISOString(),
            });
        }).fail(xhr => {
            this.app.failTopologyOperation(
                operationGeneration,
                this.failureMessage(xhr),
                null
            );
        });
        return request;
    }

    fetchState() {
        var stateSequence = ++this.stateRequestSequence;
        this.request('sonos', '$room', 'state').done((resp, _textStatus, xhr) => {
            if (stateSequence !== this.stateRequestSequence) {
                return;
            }
            var parsed = this.parseJsonMaybe(resp);
            if (!parsed) {
                this.pubsub.submit('Room.StateObserved', {
                    State: null,
                    Meta: {unknown: true, statusCode: 502},
                    RequestSequence: stateSequence,
                });
                return;
            }
            this.pubsub.submit('Room.StateObserved', {
                State: parsed,
                Meta: this.responseMeta(xhr),
                RequestSequence: stateSequence,
            });
        }).fail(xhr => {
            if (stateSequence !== this.stateRequestSequence) {
                return;
            }
            this.pubsub.submit('Room.StateObserved', {
                State: null,
                Meta: {
                    unknown: true,
                    statusCode: (xhr && xhr.status) || 0,
                },
                RequestSequence: stateSequence,
            });
        });

        var zonesSequence = ++this.zonesRequestSequence;
        this.request('sonos', 'zones').done((resp, _textStatus, xhr) => {
            if (zonesSequence !== this.zonesRequestSequence) {
                return;
            }
            var parsed = this.parseJsonMaybe(resp);
            if (!parsed) {
                this.pubsub.submit('Room.ZonesObserved', {
                    Zones: null,
                    Meta: {unknown: true, statusCode: 502},
                    RequestSequence: zonesSequence,
                });
                return;
            }
            this.pubsub.submit('Room.ZonesObserved', {
                Zones: parsed,
                Meta: this.responseMeta(xhr),
                RequestSequence: zonesSequence,
            });
        }).fail(xhr => {
            if (zonesSequence !== this.zonesRequestSequence) {
                return;
            }
            this.pubsub.submit('Room.ZonesObserved', {
                Zones: null,
                Meta: {
                    unknown: true,
                    statusCode: (xhr && xhr.status) || 0,
                },
                RequestSequence: zonesSequence,
            });
        });

        var statusSequence = ++this.statusRequestSequence;
        this.request('sonos-intents', 'status').done(resp => {
            if (statusSequence !== this.statusRequestSequence) {
                return;
            }
            var parsed = this.parseJsonMaybe(resp);
            if (!parsed) {
                return;
            }
            this.pubsub.submit('Intent.StateObserved', {
                Status: parsed,
                RequestSequence: statusSequence,
            });
        });
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        MusicController: MusicController,
    };
}
