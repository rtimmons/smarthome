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

        this.ledgridController = new LedGridController({
            requester: this,
            root: '', // Empty root for relative URLs (ingress compatible)
            app: this,
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

        this.bannerAnimationFrame = null;
        this.bannerAnimationStartedAt = null;
        this.bannerPixelsPerSecond = 100;
        this.trackBanner = '';
        this.intentBanner = '';
        this.renderedBanner = '';
        this.intentBannerHasError = false;
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

    _bannerCell() {
        return this.$.find('.state-Music');
    }

    _stopBannerAnimation() {
        if (this.bannerAnimationFrame !== null) {
            this.window.cancelAnimationFrame(this.bannerAnimationFrame);
            this.bannerAnimationFrame = null;
        }
        this.bannerAnimationStartedAt = null;
    }

    _renderBannerFrame($track, loopWidth, timestamp) {
        if (!$track || !$track.length || !loopWidth) {
            return;
        }

        if (this.bannerAnimationStartedAt === null) {
            this.bannerAnimationStartedAt = timestamp;
        }

        var elapsedSeconds = (timestamp - this.bannerAnimationStartedAt) / 1000;
        var distance =
            (elapsedSeconds * this.bannerPixelsPerSecond) % loopWidth;
        $track.css('transform', 'translateX(' + -distance + 'px)');

        this.bannerAnimationFrame = this.window.requestAnimationFrame(ts =>
            this._renderBannerFrame($track, loopWidth, ts)
        );
    }

    _restartBannerAnimation($track, segmentWidth) {
        if (!$track || !$track.length) {
            return;
        }
        var wrapper = $track.closest('.banner-marquee');
        if (!wrapper.length) {
            return;
        }

        this._stopBannerAnimation();
        $track.css('transform', 'translateX(0px)');
        $track.css('width', '');

        var firstSegmentWidth =
            segmentWidth || $track.children().first().outerWidth(true);
        var wrapperWidth = wrapper.innerWidth();
        if (!firstSegmentWidth || !wrapperWidth) {
            return;
        }

        $track.css('width', firstSegmentWidth * $track.children().length + 'px');
        this.bannerAnimationFrame = this.window.requestAnimationFrame(ts =>
            this._renderBannerFrame($track, firstSegmentWidth, ts)
        );
    }

    _setRenderedBanner(msg) {
        var bannerText = (msg || '').trim();
        var track = this._ensureBannerTrack();
        if (!track.length) {
            return;
        }

        if (!bannerText) {
            track.empty();
            this._stopBannerAnimation();
            track.css('transform', 'translateX(0px)');
            this.renderedBanner = '';
            return;
        }

        if (bannerText === this.renderedBanner) {
            return;
        }

        track.empty();
        var segment = this._createBannerSegment(bannerText);
        var wrapperWidth = track.closest('.banner-marquee').innerWidth() || 0;
        var probe = segment.clone();
        track.append(probe);
        var segmentWidth = probe.outerWidth(true);
        track.empty();

        var repeatCount = 2;
        if (segmentWidth > 0 && wrapperWidth > 0) {
            repeatCount = Math.max(3, Math.ceil(wrapperWidth / segmentWidth) + 2);
        }

        for (var i = 0; i < repeatCount; i++) {
            track.append(segment.clone());
        }
        track.attr('title', bannerText);
        this.renderedBanner = bannerText;
        this._restartBannerAnimation(track, segmentWidth);
    }

    _refreshBanner() {
        this._bannerCell().toggleClass('intent-error', this.intentBannerHasError);
        this._setRenderedBanner(this.intentBanner || this.trackBanner);
    }

    setTrackBanner(msg) {
        this.trackBanner = (msg || '').trim();
        this._refreshBanner();
    }

    setIntentBanner(msg, hasError) {
        this.intentBanner = (msg || '').trim();
        this.intentBannerHasError = Boolean(hasError && this.intentBanner);
        this._refreshBanner();
    }

    // TODO: remove after callers migrate to setTrackBanner
    setBanner(msg) {
        this.setTrackBanner(msg);
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
        var myZone = zones.filter(z => z.members.indexOf(this.room) >= 0)[0];
        if (!myZone || !Array.isArray(myZone.members)) {
            return;
        }
        var sameZone = myZone.members;
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
            case 'LedGrid.Start':
                this.ledgridController.start(params[0], params[1]);
                break;
            case 'LedGrid.Stop':
                this.ledgridController.stop();
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
