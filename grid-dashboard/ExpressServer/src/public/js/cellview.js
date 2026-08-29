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

        // Touch events do not reliably emit dblclick. Delay only cells that
        // actually have a double-press action, then commit exactly one event.
        /**
         * @type {boolean|function|null}
         */
        var tapped = false;
        $element.on('touchstart', function(e) {
            if (!pressDispatcher.hasDouble()) {
                pressDispatcher.commitSingle();
                e.preventDefault();
                return;
            }
            if (!tapped) {
                tapped = setTimeout(function() {
                    tapped = null;
                    pressDispatcher.commitSingle();
                }, 300);
            } else {
                clearTimeout(tapped);
                tapped = null;
                pressDispatcher.double();
            }
            e.preventDefault();
        });

        // Native desktop dblclick fires after click events. Hold the single
        // action briefly so the double action can cancel it instead of firing
        // room-off and all-off together.
        $element.on('click', () => pressDispatcher.single());
        $element.on('dblclick', () => pressDispatcher.double());
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
    };
}
