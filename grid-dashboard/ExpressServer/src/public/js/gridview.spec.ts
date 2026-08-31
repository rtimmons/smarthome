import { expect } from 'chai';

const { GridView }: any = require('./gridview');

describe('GridView zone state', () => {
    it('restores the active room after a responsive grid rebuild', () => {
        const grid = new GridView({
            container: {},
            config: {cols: 1, rows: 1},
            pubsub: {},
        });
        const calls: Array<[string, boolean]> = [];
        grid.cells = [
            {
                config: {activeWhenRoom: 'Kitchen'},
                isActiveForRoom: (room: string) => room === 'Kitchen',
                setActive: (enabled: boolean) =>
                    calls.push(['Kitchen', enabled]),
            },
            {
                config: {activeWhenRoom: 'Office'},
                isActiveForRoom: (room: string) => room === 'Office',
                setActive: (enabled: boolean) =>
                    calls.push(['Office', enabled]),
            },
            {
                config: {},
                setActive: () => undefined,
            },
        ];

        grid.setActiveRoom('Kitchen');

        expect(calls).to.deep.equal([
            ['Kitchen', true],
            ['Office', false],
        ]);
    });

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

describe('GridView sizing', () => {
    const originalDollar = (globalThis as any).$;

    afterEach(() => {
        (globalThis as any).$ = originalDollar;
    });

    it('keeps every column within an evenly divisible viewport', () => {
        const assignedWidths: number[] = [];
        const container = {
            width(value: number) {
                assignedWidths.push(value);
            },
        };
        const cellStyles: Record<string, string> = {};
        const cell = {
            attr() {
                return undefined;
            },
            css(styles: Record<string, string>) {
                Object.assign(cellStyles, styles);
            },
        };
        (globalThis as any).$ = (target: unknown) =>
            target === cell
                ? cell
                : {
                      each(callback: (this: typeof cell) => void) {
                          callback.call(cell);
                      },
                  };
        const grid = new GridView({
            container,
            config: {cols: 11, rows: 8},
            pubsub: {},
        });

        grid.onResize(440, 956);

        expect(grid.square).to.equal(40);
        expect(cellStyles.width).to.equal('40px');
        expect(assignedWidths).to.deep.equal([440]);
    });

    it('rounds cell size down so uneven viewports cannot overflow', () => {
        const assignedWidths: number[] = [];
        const container = {
            width(value: number) {
                assignedWidths.push(value);
            },
        };
        const cell = {
            attr() {
                return undefined;
            },
            css() {},
        };
        (globalThis as any).$ = (target: unknown) =>
            target === cell
                ? cell
                : {
                      each(callback: (this: typeof cell) => void) {
                          callback.call(cell);
                      },
                  };
        const grid = new GridView({
            container,
            config: {cols: 11, rows: 8},
            pubsub: {},
        });

        grid.onResize(414, 896);

        expect(grid.square).to.equal(37);
        expect(assignedWidths).to.deep.equal([407]);
        expect(assignedWidths[0]).to.be.at.most(414);
    });
});
