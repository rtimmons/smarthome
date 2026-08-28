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
            setActive(value: boolean) {
                this.setActiveCalls.push(value);
            },
            setZoneUnknown(value: boolean) {
                this.setZoneUnknownCalls.push(value);
            },
        };
        grid.cells = [cell];

        grid.setZonesUnknown();

        expect(cell.setActiveCalls).to.deep.equal([]);
        expect(cell.setZoneUnknownCalls).to.deep.equal([true]);
    });
});
