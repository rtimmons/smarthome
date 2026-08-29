import { expect } from 'chai';

const { GridView }: any = require('./gridview');

describe('GridView zone state', () => {
    it('keeps the last observed memberships when zones become uncertain', () => {
        const grid = new GridView({
            container: {},
            config: { cols: 1, rows: 1 },
            pubsub: {},
        });
        const cell = {
            togglesRoom: () => 'Kitchen',
            setActiveCalls: [] as boolean[],
            setZoneUnknownCalls: [] as boolean[],
            setZoneStaleCalls: [] as boolean[],
            setActive(value: boolean) {
                this.setActiveCalls.push(value);
            },
            setZoneUnknown(value: boolean) {
                this.setZoneUnknownCalls.push(value);
            },
            setZoneStale(value: boolean) {
                this.setZoneStaleCalls.push(value);
            },
        };
        grid.cells = [cell];

        grid.setZonesUnknown();

        expect(cell.setActiveCalls).to.deep.equal([]);
        expect(cell.setZoneUnknownCalls).to.deep.equal([true]);
        expect(cell.setZoneStaleCalls).to.deep.equal([false]);
    });

    it('marks stale separately without changing observed memberships', () => {
        const grid = new GridView({
            container: {},
            config: {cols: 1, rows: 1},
            pubsub: {},
        });
        const cell = {
            togglesRoom: () => 'Kitchen',
            setActiveCalls: [] as boolean[],
            setZoneUnknownCalls: [] as boolean[],
            setZoneStaleCalls: [] as boolean[],
            setActive(value: boolean) {
                this.setActiveCalls.push(value);
            },
            setZoneUnknown(value: boolean) {
                this.setZoneUnknownCalls.push(value);
            },
            setZoneStale(value: boolean) {
                this.setZoneStaleCalls.push(value);
            },
        };
        grid.cells = [cell];

        grid.setZonesStale(true);

        expect(cell.setActiveCalls).to.deep.equal([]);
        expect(cell.setZoneUnknownCalls).to.deep.equal([false]);
        expect(cell.setZoneStaleCalls).to.deep.equal([true]);
    });

    it('recovers stale then unknown presentation when fresh memberships arrive', () => {
        const grid = new GridView({
            container: {},
            config: {cols: 1, rows: 1},
            pubsub: {},
        });
        const cell = {
            togglesRoom: () => 'Kitchen',
            setActiveCalls: [] as boolean[],
            setZoneUnknownCalls: [] as boolean[],
            setZoneStaleCalls: [] as boolean[],
            setActive(value: boolean) {
                this.setActiveCalls.push(value);
            },
            setZoneUnknown(value: boolean) {
                this.setZoneUnknownCalls.push(value);
            },
            setZoneStale(value: boolean) {
                this.setZoneStaleCalls.push(value);
            },
        };
        grid.cells = [cell];

        grid.setZonesStale(true);
        grid.setZonesUnknown();
        grid.updateZones({on: ['Kitchen'], off: []});

        expect(cell.setActiveCalls).to.deep.equal([true]);
        expect(cell.setZoneUnknownCalls).to.deep.equal([false, true, false]);
        expect(cell.setZoneStaleCalls).to.deep.equal([true, false, false]);
    });
});
