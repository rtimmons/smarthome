const log = console.log;

class App {
    constructor(args) {
        this.window = args.window;
        this.$ = args.container;
        this.grid = args.grid;
        this.config = args.config;
        this.baseConfig = args.config;
        this.rooms = args.config.rooms;
        this.pubsub = args.pubsub;

        // TODO: move to object-factory
        this.musicController = new MusicController({
            requester: this,
            root: '', // Empty root for relative URLs (ingress compatible)
            app: this,
            pubsub: this.pubsub,
        });

        // TODO: move to object-factory
        this.lightController = new LightController({
            requester: this,
            root: '', // Empty root for relative URLs (ingress compatible)
            app: this,
            pubsub: this.pubsub,
        });

        this.printerController = new PrinterController({
            app: this,
            port: this.config.printerPort,
        });

        // TODO: move to object-factory
        this.blindControllerI2c = new BlindControllerI2C({
            requester: this,
            root: '', // Empty root for relative URLs (ingress compatible)
            app: this,
            pubsub: this.pubsub,
        });


        // TODO: move to pubsub class
        this.pubsub.subscribe('*', {
            onMessage: e => {
                this.eachCell(c => c.onMessage(e));
                this.musicController.onMessage(e);
            },
        });
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
            var f = () =>
                this.onAction(p.action, p.args, { Submitted: new Date() });
            setInterval(f, p.period);
        });
    }

    _ensureBannerTrack() {
        if (this.$bannerTrack && this.$bannerTrack.length) {
            return this.$bannerTrack;
        }
        var bannerContent = this.$.find('.state-Music .content');
        if (!bannerContent.length) {
            return $();
        }
        bannerContent.empty();
        var marquee = $('<div class="banner-marquee"></div>');
        this.$bannerTrack = $('<div class="banner-marquee__track"></div>');
        marquee.append(this.$bannerTrack);
        bannerContent.append(marquee);
        return this.$bannerTrack;
    }

    _createBannerSegment(text) {
        return $('<span class="banner-marquee__segment"></span>').text(text);
    }

    _restartBannerAnimation($track, segmentWidth) {
        if (!$track || !$track.length) {
            return;
        }
        var wrapper = $track.closest('.banner-marquee');
        if (!wrapper.length) {
            return;
        }

        // Reset animation state so a new track always starts from the right edge.
        $track.removeClass('banner-marquee__track--scroll');

        var firstSegmentWidth =
            segmentWidth || $track.children().first().outerWidth(true);
        if (!firstSegmentWidth) {
            return;
        }
        var start = 0;
        var end = -firstSegmentWidth;
        if (!isFinite(end)) {
            return;
        }

        $track.css('--marquee-start', start + 'px');
        $track.css('--marquee-end', end + 'px');

        var distance = start - end; // distance equal to first segment width
        var pixelsPerSecond = 160;
        var durationSeconds = Math.max(distance / pixelsPerSecond, 8);
        $track.css('animation-duration', durationSeconds + 's');

        // Force reflow before enabling the animation class again.
        void $track[0].offsetWidth;

        $track.addClass('banner-marquee__track--scroll');
    }

    // TODO: move to gridview?
    setBanner(msg) {
        var bannerText = (msg || '').trim();
        var track = this._ensureBannerTrack();
        if (!track.length) {
            return;
        }

        if (!bannerText) {
            track.empty();
            track.removeClass('banner-marquee__track--scroll');
            this.banner = '';
            return;
        }

        if (bannerText === this.banner) {
            return;
        }

        track.empty();
        var segment = this._createBannerSegment(bannerText);
        var duplicate = segment.clone();
        track.append(segment, duplicate);
        track.attr('title', bannerText);
        var segmentWidth = segment.outerWidth(true);
        this.banner = bannerText;
        this._restartBannerAnimation(track, segmentWidth);
    }

    // TODO: move to gridview?
    setBackgroundImage(url) {
        if (url === this.backgroundImage) {
            return;
        }
        if (url) {
            $('#grid-container').css({ backgroundImage: 'url("' + url + '")' });
        } else {
            $('#grid-container').css({ backgroundImage: '' });
        }
        this.backgroundImage = url;
    }

    /**
     * zones is like
     * [ {members: [list string room names]} ]
     */
    updateZones(zones) {
        var sameZone = zones.filter(z => z.members.indexOf(this.room) >= 0)[0]
            .members;
        var arg = {
            on: sameZone,
            off: this.rooms.filter(r => sameZone.indexOf(r) < 0),
        };
        this.grid.updateZones(arg);
    }

    currentRoom() {
        return this.room;
    }

    _applyRoomConfig(roomName) {
        if (!this.baseConfig || !this.baseConfig.roomOverrides) {
            return;
        }
        var resolved = ConfigResolver.resolveRoomConfig(
            this.baseConfig,
            roomName
        );
        if (resolved === this.config) {
            return;
        }
        this.config = resolved;
        this.grid.updateCells(resolved.cells);
    }

    changeRoom(toRoom) {
        var oldRoom = this.room;
        this.room = toRoom;
        this._applyRoomConfig(toRoom);
        this.pubsub.submit('Room.Changed', {
            FromRoom: oldRoom,
            ToRoom: toRoom,
        });
    }

    // TODO: move to request class?
    request(url) {
        var params =
            typeof url === 'object'
                ? url
                : {
                      url: url,
                      error: (xhr, st, err) => console.log(url, err),
                  };
        return $.ajax(params);
    }

    // TODO: don't call directly/ expose musicController?
    fetchState() {
        this.musicController.fetchState();
    }

    // TODO: move to action listeners
    onAction(action, params, evt) {
        // only process events that have happened in the last 500 milliseconds
        if (new Date().getTime() - evt.Submitted.getTime() > 500) {
            console.log('Event too old ' + evt.Submitted);
            return;
        }
        switch (action) {
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
            case 'Lights.Scene':
                this.lightController.scene(params);
                break;

            case 'Blinds.Move':
                this.blindControllerI2c.move(params);
                break;

            // TODO: move to Music.* listeners to MusicController
            case 'Music.ToggleRoom':
                if (evt.Event.Cell.isActive()) {
                    this.musicController.leaveRoom(params[0]);
                } else {
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
            case 'Printer.Preset':
                this.printerController.preset(params[0]);
                break;
            case 'Music.VolumeUp':
                this.musicController.volumeUp();
                break;
            case 'Music.VolumeDown':
                this.musicController.volumeDown();
                break;
            case 'Music.VolumeSame':
                this.musicController.volumeSame();
                break;
            case 'Music.SetVolume':
                this.musicController.setVolume(params[0]);
                break;
            case 'Music.Next':
                this.musicController.next();
                break;

                consle.error('Unknown action ' + action);
        }
    }
}
