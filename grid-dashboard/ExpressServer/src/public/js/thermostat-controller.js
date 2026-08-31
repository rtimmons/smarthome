function formatTemperature(value) {
    if (value === undefined || value === null || value === '') {
        return '';
    }
    var temperature = Number(value);
    if (!Number.isFinite(temperature)) {
        return '';
    }
    return Math.round(temperature * 10) / 10 + '°';
}

class ThermostatController {
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

    parseJsonMaybe(value) {
        if (typeof value !== 'string') {
            return value;
        }
        try {
            return JSON.parse(value);
        } catch (err) {
            console.log('Failed to parse thermostat response as JSON', err);
            return null;
        }
    }

    fetchState() {
        var room = this.app.currentRoom();
        if (!room) {
            return;
        }

        this.requester
            .request(
                this.resolveUrl('thermostats/' + encodeURIComponent(room))
            )
            .done(resp => {
                var parsed = this.parseJsonMaybe(resp);
                if (!parsed || parsed.room !== room) {
                    return;
                }
                this.pubsub.submit('Thermostat.StateObserved', {
                    Room: parsed.room,
                    Thermostat: parsed.thermostat,
                });
            })
            .fail(() => {
                this.pubsub.submit('Thermostat.StateObserved', {
                    Room: room,
                    Thermostat: null,
                });
            });
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        formatTemperature: formatTemperature,
        ThermostatController: ThermostatController,
    };
}
