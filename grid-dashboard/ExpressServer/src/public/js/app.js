const log = console.log;

function bannerTrackIsCurrent(bannerContent, bannerTrack) {
    return Boolean(
        bannerContent &&
        bannerContent.length &&
        bannerContent[0] &&
        bannerTrack &&
        bannerTrack.length &&
        bannerContent[0].contains(bannerTrack[0])
    );
}

function layoutMatchesViewport(rule, width, height) {
    if (!rule || !width || !height) {
        return false;
    }
    if (rule.orientation === 'portrait' && height <= width) {
        return false;
    }
    if (rule.orientation === 'landscape' && width <= height) {
        return false;
    }
    if (rule.minWidth !== undefined && width < rule.minWidth) {
        return false;
    }
    if (rule.maxWidth !== undefined && width > rule.maxWidth) {
        return false;
    }
    if (rule.minHeight !== undefined && height < rule.minHeight) {
        return false;
    }
    if (rule.maxHeight !== undefined && height > rule.maxHeight) {
        return false;
    }
    return true;
}

function layoutNameForViewport(windowObject, config) {
    var width = Number(windowObject && windowObject.innerWidth);
    var height = Number(windowObject && windowObject.innerHeight);
    var layoutOverrides = (config && config.layoutOverrides) || {};
    var layoutNames = Object.keys(layoutOverrides);

    for (var i = 0; i < layoutNames.length; i++) {
        var layoutName = layoutNames[i];
        if (
            layoutMatchesViewport(
                layoutOverrides[layoutName].when,
                width,
                height
            )
        ) {
            return layoutName;
        }
    }
    return 'default';
}

class App {
    constructor(args) {
        this.window = args.window;
        this.$ = args.container;
        this.grid = args.grid;
        this.baseConfig = args.config;
        this.layoutMode = layoutNameForViewport(
            this.window,
            this.baseConfig
        );
        this.config = ConfigResolver.resolveLayoutConfig(
            this.baseConfig,
            this.layoutMode
        );
        this.rooms = args.config.rooms;
        this.pubsub = args.pubsub;
        this.now = args.now || function() {
            return new Date().getTime();
        };

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
            sceneRooms: this.config.lightSceneRooms,
        });

        this.thermostatController = new ThermostatController({
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
        this.topologyBanner = '';
        this.renderedBanner = '';
        this.intentBannerHasError = false;
        this.sonosStateIsStale = false;
        this.sonosStateIsUnknown = true;
        this.zoneStateIsUnknown = true;
        this.zoneStateFreshness = 'unknown';
        this.knownZones = null;
        this.intentStatus = {};
        this.pendingZoneMutations = {};
        this.thermostatStates = {};
        this.zoneMutationTimeoutMs = SONOS_ZONE_MUTATION_TIMEOUT_MS;
        this.topologyOperationGate = new SonosOperationGate();
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
        this.grid.init($(this.window), this, this.config);
        this._bindLayoutWatcher();
        this.setZonesUnknown(true);
        this.setSonosMediaFreshness('unknown');

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

    _bindLayoutWatcher() {
        $(this.window).on('resize orientationchange', () => {
            this._syncLayoutMode();
        });
        this._markLayoutMode();
    }

    _markLayoutMode() {
        var body =
            this.window && this.window.document
                ? this.window.document.body
                : null;
        if (body) {
            body.setAttribute('data-dashboard-layout', this.layoutMode);
        }
    }

    _syncLayoutMode() {
        var nextLayoutMode = layoutNameForViewport(
            this.window,
            this.baseConfig
        );
        if (nextLayoutMode === this.layoutMode) {
            return false;
        }

        this.layoutMode = nextLayoutMode;
        this._markLayoutMode();
        this._applyDisplayConfig(this.room, true);
        return true;
    }

    _applyDisplayConfig(roomName, forceRebuild) {
        var resolved = ConfigResolver.resolveDisplayConfig(
            this.baseConfig,
            this.layoutMode,
            roomName
        );
        var geometryChanged =
            resolved.rows !== this.grid.rows ||
            resolved.cols !== this.grid.cols;

        this.config = resolved;
        if (forceRebuild || geometryChanged) {
            this.grid.renderConfig(resolved);
            this._restoreGridPresentation();
            return;
        }
        this.grid.updateCells(resolved.cells);
    }

    _restoreGridPresentation() {
        this.grid.setActiveRoom(this.room);

        if (this.knownZones && this.room) {
            var myZone = this.knownZones.filter(
                zone => zone.members.indexOf(this.room) >= 0
            )[0];
            if (myZone) {
                this.grid.updateZones({
                    on: myZone.members,
                    off: this.rooms.filter(
                        roomName => myZone.members.indexOf(roomName) < 0
                    ),
                });
                this.grid.setZonesStale(
                    this.zoneStateFreshness === 'stale'
                );
            } else {
                this.grid.setZonesUnknown();
            }
        } else if (this.zoneStateIsUnknown) {
            this.grid.setZonesUnknown();
        }

        Object.keys(this.pendingZoneMutations).forEach(roomName => {
            this.grid.setZoneMutationPending(roomName, true);
        });
        this.grid.updateIntent(reconcileIntentStatus(
            this.intentStatus,
            this.knownZones
        ));

        this.$bannerTrack = null;
        this.renderedBanner = '';
        this._refreshBanner();

        if (
            this.room &&
            Object.prototype.hasOwnProperty.call(
                this.thermostatStates,
                this.room
            )
        ) {
            this.setThermostatState(
                this.room,
                this.thermostatStates[this.room]
            );
        }
    }

    _ensureBannerTrack() {
        var bannerContent = this.$.find('.state-Music .content');
        if (!bannerContent.length) {
            return $();
        }
        if (bannerTrackIsCurrent(bannerContent, this.$bannerTrack)) {
            return this.$bannerTrack;
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
        this._bannerCell().toggleClass('stale', this.sonosStateIsStale);
        this._bannerCell().toggleClass('unknown', this.sonosStateIsUnknown);
        this._setRenderedBanner(
            this.intentBanner || this.topologyBanner || this.trackBanner
        );
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

    setSonosStateStale(isStale) {
        this.sonosStateIsStale = Boolean(isStale);
        this.sonosStateIsUnknown = false;
        this._refreshBanner();
    }

    setSonosMediaFreshness(freshness) {
        this.sonosStateIsStale = freshness === 'stale';
        this.sonosStateIsUnknown = freshness === 'unknown';
        this._refreshBanner();
    }

    setThermostatState(room, thermostat) {
        this.thermostatStates[room] = thermostat;
        if (room !== this.currentRoom()) {
            return;
        }

        var cell = this.$.find('.state-Thermostat');
        var currentTemperature = thermostat
            ? thermostat.currentTemperature
            : null;
        var displayTemperature = formatTemperature(currentTemperature);
        var hasTemperature = Boolean(displayTemperature);
        var temperatureUnit =
            thermostat && thermostat.temperatureUnit
                ? ' ' + thermostat.temperatureUnit
                : '';

        cell.toggleClass('thermostat-available', hasTemperature);
        cell.children('.content').text(displayTemperature);
        if (hasTemperature) {
            cell.attr(
                'title',
                room + ': ' + currentTemperature + temperatureUnit
            );
        } else {
            cell.removeAttr('title');
        }
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
    updateZones(zones, meta) {
        var myZone = zones.filter(z => z.members.indexOf(this.room) >= 0)[0];
        if (!myZone || !Array.isArray(myZone.members)) {
            this.setZonesUnknown(true);
            return;
        }
        this.knownZones = zones;
        this.zoneStateFreshness = 'live';
        var unavailableRooms = meta && Array.isArray(meta.unavailableRooms)
            ? meta.unavailableRooms
            : [];
        this.topologyBanner = unavailableRooms.length > 0
            ? 'Sonos unavailable: ' + unavailableRooms.join(', ')
            : '';
        this.setZonesUnknown(false);
        this.grid.setZonesStale(false);
        var sameZone = myZone.members;
        var arg = {
            on: sameZone,
            off: this.rooms.filter(r => sameZone.indexOf(r) < 0),
        };
        this.grid.updateZones(arg);
        this._reconcileZoneMutations(zones);
        this._refreshIntentPresentation();
    }

    setZonesUnknown(isUnknown) {
        this.zoneStateIsUnknown = Boolean(isUnknown);
        if (this.zoneStateIsUnknown) {
            this.zoneStateFreshness = 'unknown';
            this.topologyBanner = 'Sonos groups unavailable';
            this.grid.setZonesUnknown();
        } else {
            this.grid.clearZonesUnknown();
        }
        this._refreshBanner();
    }

    setZonesStale(meta, zones) {
        if (Array.isArray(zones) && zones.length > 0) {
            var myZone = zones.filter(z => z.members.indexOf(this.room) >= 0)[0];
            if (!myZone || !Array.isArray(myZone.members)) {
                this.setZonesUnknown(true);
                return;
            }
            this.knownZones = zones;
            this.grid.updateZones({
                on: myZone.members,
                off: this.rooms.filter(r => myZone.members.indexOf(r) < 0),
            });
            this._reconcileZoneMutations(zones);
            this._refreshIntentPresentation();
        }
        if (!this.knownZones) {
            this.setZonesUnknown(true);
            return;
        }

        this.zoneStateIsUnknown = false;
        this.zoneStateFreshness = 'stale';
        var ageMs = Number(meta && meta.ageMs);
        var ageText = Number.isFinite(ageMs) && ageMs > 0
            ? ' (' + Math.round(ageMs / 1000) + 's)'
            : '';
        this.topologyBanner = 'Sonos groups stale' + ageText;
        this.grid.setZonesStale(true);
        this._refreshBanner();
    }

    updateIntentStatus(status) {
        var filtered = this.topologyOperationGate.filterStatus(status || {});
        if (filtered === null) {
            return false;
        }
        this.intentStatus = filtered;
        this._reconcilePendingOperationStatus(filtered);
        this._refreshIntentPresentation();
        return true;
    }

    beginTopologyOperation() {
        var generation = this.topologyOperationGate.begin();
        Object.keys(this.pendingZoneMutations).forEach(roomName => {
            this._clearZoneMutation(roomName);
        });
        this.intentStatus = {};
        this.grid.updateIntent({});
        this.setIntentBanner('', false);
        return generation;
    }

    acceptTopologyOperation(generation, response) {
        var operation = this.topologyOperationGate.acceptResponse(
            generation,
            response
        );
        if (!operation || !operation.id) {
            return operation;
        }

        Object.keys(this.pendingZoneMutations).forEach(roomName => {
            var mutation = this.pendingZoneMutations[roomName];
            if (mutation.operationGeneration === generation) {
                mutation.operationId = operation.id;
            }
        });
        this._reconcilePendingOperationStatus({
            activeIntent: operation.status === 'running' ? operation : null,
            recentIntent: operation.status === 'running' ? null : operation,
        });
        return operation;
    }

    failTopologyOperation(generation, message, roomName) {
        if (!this.topologyOperationGate.fail(generation)) {
            return false;
        }

        if (roomName) {
            var mutation = this.pendingZoneMutations[roomName];
            if (mutation && mutation.operationGeneration === generation) {
                this._clearZoneMutation(roomName);
            }
        }
        this.setIntentBanner(message || 'Sonos grouping request failed', true);
        return true;
    }

    _refreshIntentPresentation() {
        var status = reconcileIntentStatus(
            this.intentStatus,
            this.knownZones
        );
        this.grid.updateIntent(status);
        this.setIntentBanner(
            intentBannerText(status),
            intentHasError(status)
        );
    }

    _clearZoneMutation(roomName) {
        var mutation = this.pendingZoneMutations[roomName];
        if (mutation && mutation.timeoutHandle) {
            this.window.clearTimeout(mutation.timeoutHandle);
        }
        delete this.pendingZoneMutations[roomName];
        this.grid.setZoneMutationPending(roomName, false);
    }

    _reconcilePendingOperationStatus(status) {
        var operation = terminalOperationFromStatus(status);
        if (!operation || !operation.id) {
            return;
        }

        Object.keys(this.pendingZoneMutations).forEach(roomName => {
            var mutation = this.pendingZoneMutations[roomName];
            if (mutation.operationId === operation.id) {
                this._clearZoneMutation(roomName);
            }
        });
    }

    _expireZoneMutation(roomName, operationGeneration) {
        var mutation = this.pendingZoneMutations[roomName];
        if (
            !mutation ||
            mutation.operationGeneration !== operationGeneration
        ) {
            return;
        }
        this._clearZoneMutation(roomName);
        this.failTopologyOperation(
            operationGeneration,
            'Sonos grouping request timed out',
            null
        );
    }

    _reconcileZoneMutations(zones) {
        var now = this.now();
        Object.keys(this.pendingZoneMutations).forEach(roomName => {
            var mutation = this.pendingZoneMutations[roomName];
            if (
                zoneMutationSatisfied(mutation, zones) ||
                now >= mutation.expiresAt
            ) {
                this._clearZoneMutation(roomName);
            }
        });
    }

    _toggleRoomMembership(roomName, cell) {
        if (!topologyMutationAllowed(this.zoneStateFreshness)) {
            this.setIntentBanner(
                this.zoneStateFreshness === 'stale'
                    ? 'Sonos groups are stale; grouping is temporarily disabled'
                    : 'Sonos groups are unavailable; grouping is disabled',
                true
            );
            return false;
        }
        var now = this.now();
        var existing = this.pendingZoneMutations[roomName];
        if (existing && now < existing.expiresAt) {
            return;
        }
        if (existing) {
            this._clearZoneMutation(roomName);
        }

        var currentlyJoined = cell.isActive();
        var operationGeneration = this.beginTopologyOperation();
        var mutation = {
            room: roomName,
            anchorRoom: this.room,
            desiredJoined: !currentlyJoined,
            expiresAt: now + this.zoneMutationTimeoutMs,
            operationGeneration: operationGeneration,
            operationId: null,
            timeoutHandle: null,
        };
        mutation.timeoutHandle = this.window.setTimeout(
            () => this._expireZoneMutation(roomName, operationGeneration),
            this.zoneMutationTimeoutMs
        );
        this.pendingZoneMutations[roomName] = mutation;
        this.grid.setZoneMutationPending(roomName, true);

        if (currentlyJoined) {
            this.musicController.leaveRoom(roomName, operationGeneration);
        } else {
            this.musicController.joinRoom(
                roomName,
                this.room,
                operationGeneration
            );
        }
        return true;
    }

    currentRoom() {
        return this.room;
    }

    _applyRoomConfig(roomName) {
        if (!this.baseConfig) {
            return;
        }
        this._applyDisplayConfig(roomName, false);
    }

    changeRoom(toRoom) {
        var oldRoom = this.room;
        this.room = toRoom;
        this._applyRoomConfig(toRoom);
        this.setThermostatState(toRoom, null);
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

    fetchThermostatState() {
        this.thermostatController.fetchState();
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
                if (!topologyMutationAllowed(this.zoneStateFreshness)) {
                    this.setIntentBanner(
                        this.zoneStateFreshness === 'stale'
                            ? 'Sonos groups are stale; join-all is temporarily disabled'
                            : 'Sonos groups are unavailable; join-all is disabled',
                        true
                    );
                    break;
                }
                this.musicController.allJoin(
                    params[0],
                    this.beginTopologyOperation()
                );
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
                this._toggleRoomMembership(params[0], evt.Event.Cell);
                break;
            case 'Music.FetchState':
                this.fetchState();
                break;
            case 'Thermostat.FetchState':
                this.fetchThermostatState();
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
                if (!topologyMutationAllowed(this.zoneStateFreshness)) {
                    this.setIntentBanner(
                        this.zoneStateFreshness === 'stale'
                            ? 'Sonos groups are stale; presets are temporarily disabled'
                            : 'Sonos groups are unavailable; presets are disabled',
                        true
                    );
                    break;
                }
                this.musicController.preset(
                    params[0],
                    this.beginTopologyOperation()
                );
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

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        App: App,
        bannerTrackIsCurrent: bannerTrackIsCurrent,
        layoutMatchesViewport: layoutMatchesViewport,
        layoutNameForViewport: layoutNameForViewport,
    };
}
