class PressDispatcher {
    constructor(args) {
        this.onSingle = args.onSingle;
        this.onDouble = args.onDouble;
        this.hasDouble = args.hasDouble;
        // Wrap browser timer globals so they are invoked with their native
        // receiver instead of as methods on this dispatcher.
        this.schedule =
            args.schedule || ((callback, delay) => setTimeout(callback, delay));
        this.cancel = args.cancel || (timer => clearTimeout(timer));
        this.delay = args.delay === undefined ? 300 : args.delay;
        this.pending = null;
    }

    single() {
        if (!this.hasDouble()) {
            this.commitSingle();
            return;
        }
        if (this.pending) {
            this.cancel(this.pending);
        }
        this.pending = this.schedule(() => {
            this.pending = null;
            this.onSingle();
        }, this.delay);
    }

    commitSingle() {
        if (this.pending) {
            this.cancel(this.pending);
            this.pending = null;
        }
        this.onSingle();
    }

    double() {
        if (this.pending) {
            this.cancel(this.pending);
            this.pending = null;
        }
        if (this.hasDouble()) {
            this.onDouble();
        }
    }
}

function bindCellPressEvents($element, pressDispatcher, options) {
    options = options || {};
    var now = options.now || function() {
        return new Date().getTime();
    };
    var schedule = options.schedule || function(callback, delay) {
        return setTimeout(callback, delay);
    };
    var cancel = options.cancel || function(timer) {
        clearTimeout(timer);
    };
    var tapped = null;
    var ignoreClicksUntil = 0;

    // Complete touch gestures on touchend. FastClick can synthesize a click
    // for the same gesture, so remember the touch and ignore that duplicate.
    // Handling touchstart directly made a single tap travel through both
    // paths on mobile webviews and left the result browser-dependent.
    $element.on('touchend', function(e) {
        ignoreClicksUntil = now() + 500;
        if (!pressDispatcher.hasDouble()) {
            pressDispatcher.commitSingle();
            e.preventDefault();
            return;
        }
        if (!tapped) {
            tapped = schedule(function() {
                tapped = null;
                pressDispatcher.commitSingle();
            }, 300);
        } else {
            cancel(tapped);
            tapped = null;
            pressDispatcher.double();
        }
        e.preventDefault();
    });

    $element.on('touchcancel', function() {
        if (tapped) {
            cancel(tapped);
            tapped = null;
        }
    });

    $element.on('click', function() {
        if (now() < ignoreClicksUntil) {
            return;
        }
        pressDispatcher.single();
    });
    $element.on('dblclick', function() {
        if (now() < ignoreClicksUntil) {
            return;
        }
        pressDispatcher.double();
    });
}

class CellView {
    constructor(args) {
        // $element, config, app
        this.$element = args.$element;
        this.config = args.config;
        this.app = args.app;
        this.active = false;
        this.zoneUnknown = false;
        this.pubsub = args.pubsub;

        // console.log('args', args);

        this.setContent(this.app.emojiWithName(this.config.emoji));
        this.$element.addClass(this.config.claz || '');

        var $element = this.$element;
        var pressDispatcher = new PressDispatcher({
            onSingle: () =>
                this.pubsub.submit('Cell.Press', { Cell: this }),
            onDouble: () =>
                this.pubsub.submit('Cell.DoublePress', { Cell: this }),
            hasDouble: () => Boolean(this.config.onDoublePress),
        });

        bindCellPressEvents($element, pressDispatcher);
    }

    setContent(c) {
        this.$element.children('.content').html(c || '');
    }

    onMessage(e) {}

    updateConfig(nextConfig) {
        if (this.config.claz) {
            this.$element.removeClass(this.config.claz);
        }

        this.config = nextConfig;
        if (this.config.claz) {
            this.$element.addClass(this.config.claz);
        }

        this._refreshZoneContent();
    }

    togglesRoom() {
        return this.config.togglesRoom;
    }

    isActiveForRoom(room) {
        return this.config.activeWhenRoom === room;
    }

    isActive() {
        return this.active;
    }

    setActive(isActive) {
        var existing = this.active;
        if (isActive === existing) {
            return;
        }
        if (isActive) {
            this.$element.addClass('active');
        } else {
            this.$element.removeClass('active');
        }
        this.active = isActive;
    }

    clearIntentClasses() {
        this.$element.removeClass('intent-target intent-pending intent-error');
        this.$element.css('backgroundColor', '');
    }

    setIntentClass(claz, enabled) {
        if (!claz) {
            return;
        }

        if (enabled) {
            this.$element.addClass(claz);
            return;
        }

        this.$element.removeClass(claz);
    }

    setIntentPendingStrength(strength) {
        if (!strength) {
            this.$element.css('backgroundColor', '');
            return;
        }

        this.$element.css(
            'backgroundColor',
            'rgba(122, 93, 31, ' + strength + ')'
        );
    }

    setZoneUnknown(enabled) {
        this.zoneUnknown = Boolean(enabled);
        this.$element.toggleClass('zone-unknown', this.zoneUnknown);
        this._refreshZoneContent();
    }

    setZoneStale(enabled) {
        this.$element.toggleClass('zone-stale', Boolean(enabled));
    }

    _refreshZoneContent() {
        var emojiName =
            this.zoneUnknown && this.config.togglesRoom
                ? '?'
                : this.config.emoji;
        this.setContent(this.app.emojiWithName(emojiName));
    }

    setZoneMutationPending(enabled) {
        this.$element.toggleClass(
            'zone-mutation-pending',
            Boolean(enabled)
        );
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        CellView: CellView,
        PressDispatcher: PressDispatcher,
        bindCellPressEvents: bindCellPressEvents,
    };
}
