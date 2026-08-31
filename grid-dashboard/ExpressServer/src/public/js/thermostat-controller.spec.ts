import { expect } from 'chai';

const thermostat: any = require('./thermostat-controller');
const { config }: any = require('./config');

describe('ThermostatController', () => {
    it('uses the cell immediately above the southeast music notes', () => {
        const temperatureCell = config.cells.find(
            (cell: any) => cell.x === 10 && cell.y === 6
        );
        const southeastCell = config.cells.find(
            (cell: any) => cell.x === 10 && cell.y === 7
        );

        expect(temperatureCell.claz).to.equal('state-Thermostat');
        expect(southeastCell.emoji).to.equal('Notes');
    });

    it('formats whole and fractional temperatures compactly', () => {
        expect(thermostat.formatTemperature(72)).to.equal('72°');
        expect(thermostat.formatTemperature(71.5)).to.equal('71.5°');
        expect(thermostat.formatTemperature(null)).to.equal('');
        expect(thermostat.formatTemperature('unavailable')).to.equal('');
    });

    it('fetches the active room through an ingress-safe encoded path', () => {
        const requests: string[] = [];
        const observed: Array<{ topic: string; event: unknown }> = [];
        const controller = new thermostat.ThermostatController({
            requester: {
                request(url: string) {
                    requests.push(url);
                    return {
                        done(callback: (response: unknown) => void) {
                            callback({
                                room: 'Living Room',
                                thermostat: {
                                    currentTemperature: 71,
                                    temperatureUnit: '°F',
                                },
                            });
                            return this;
                        },
                        fail() {
                            return this;
                        },
                    };
                },
            },
            root: '/ingress-token',
            app: {
                currentRoom: () => 'Living Room',
            },
            pubsub: {
                submit(topic: string, event: unknown) {
                    observed.push({ topic, event });
                },
            },
        });

        controller.fetchState();

        expect(requests).to.deep.equal([
            '/ingress-token/thermostats/Living%20Room',
        ]);
        expect(observed).to.deep.equal([
            {
                topic: 'Thermostat.StateObserved',
                event: {
                    Room: 'Living Room',
                    Thermostat: {
                        currentTemperature: 71,
                        temperatureUnit: '°F',
                    },
                },
            },
        ]);
    });

    it('clears the active room temperature when a refresh fails', () => {
        const observed: Array<{ topic: string; event: unknown }> = [];
        const request = {
            done() {
                return this;
            },
            fail(callback: () => void) {
                callback();
                return this;
            },
        };
        const controller = new thermostat.ThermostatController({
            requester: { request: () => request },
            root: '/ingress-token',
            app: { currentRoom: () => 'Office' },
            pubsub: {
                submit(topic: string, event: unknown) {
                    observed.push({ topic, event });
                },
            },
        });

        controller.fetchState();

        expect(observed).to.deep.equal([
            {
                topic: 'Thermostat.StateObserved',
                event: { Room: 'Office', Thermostat: null },
            },
        ]);
    });
});
