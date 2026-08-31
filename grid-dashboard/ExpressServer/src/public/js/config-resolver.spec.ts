import { expect } from 'chai';

const configResolver: any = require('./config-resolver');
const {config: dashboardConfig}: any = require('./config');

describe('ConfigResolver', () => {
    it('keeps the same interaction vocabulary in the phone layout', () => {
        const actionNames = (config: any) =>
            Array.from(
                new Set(
                    config.cells.flatMap((cell: any) => [
                        cell.onPress && cell.onPress.action,
                        cell.onDoublePress && cell.onDoublePress.action,
                    ]).filter(Boolean)
                )
            ).sort();
        const phoneConfig = configResolver.resolveLayoutConfig(
            dashboardConfig,
            'phonePortrait'
        );

        expect(actionNames(phoneConfig)).to.deep.equal(
            actionNames(dashboardConfig)
        );
        expect(phoneConfig.cells.filter((cell: any) => cell.togglesRoom))
            .to.have.length(dashboardConfig.rooms.length);
        expect(phoneConfig.cells.filter((cell: any) => cell.activeWhenRoom))
            .to.have.length(dashboardConfig.rooms.length);
    });

    it('merges room overrides over base cells', () => {
        const baseConfig = {
            rows: 2,
            cols: 2,
            cells: [
                { x: 0, y: 0, w: 1, h: 1, emoji: 'Base' },
                { x: 1, y: 0, w: 1, h: 1 },
                { x: 0, y: 1, w: 1, h: 1 },
                { x: 1, y: 1, w: 1, h: 1 },
            ],
            roomOverrides: {
                Office: {
                    cells: [
                        {
                            x: 0,
                            y: 0,
                            emoji: 'Override',
                            onPress: {
                                action: 'Music.Preset',
                                args: ['office'],
                            },
                        },
                    ],
                },
            },
        };

        const resolved = configResolver.resolveRoomConfig(baseConfig, 'Office');
        const cells: any[] = resolved.cells;
        const target = cells.filter(
            (cell: any) => cell.x === 0 && cell.y === 0
        )[0];

        expect(target.emoji).to.equal('Override');
        expect(target.onPress.action).to.equal('Music.Preset');
        expect(baseConfig.cells[0].emoji).to.equal('Base');
    });

    it('throws when overrides target wide base cells', () => {
        const config = {
            rows: 1,
            cols: 2,
            cells: [{ x: 0, y: 0, w: 2, h: 1 }, { x: 1, y: 0, w: 0, h: 1 }],
            roomOverrides: {
                Kitchen: {
                    cells: [{ x: 0, y: 0, emoji: 'TV' }],
                },
            },
        };

        expect(() => configResolver.validateConfig(config)).to.throw(/non-1x1/);
    });

    it('throws when overrides define wide cells', () => {
        const config = {
            rows: 1,
            cols: 2,
            cells: [{ x: 0, y: 0, w: 1, h: 1 }, { x: 1, y: 0, w: 1, h: 1 }],
            roomOverrides: {
                Kitchen: {
                    cells: [{ x: 0, y: 0, w: 2, h: 1, emoji: 'TV' }],
                },
            },
        };

        expect(() => configResolver.validateConfig(config)).to.throw(/non-1x1/);
    });

    it('throws when overrides reference unknown cells', () => {
        const config = {
            rows: 1,
            cols: 1,
            cells: [{ x: 0, y: 0, w: 1, h: 1 }],
            roomOverrides: {
                Kitchen: {
                    cells: [{ x: 1, y: 0, emoji: 'TV' }],
                },
            },
        };

        expect(() => configResolver.validateConfig(config)).to.throw(
            /unknown cell/
        );
    });

    it('resolves layout placement before applying that layout room override', () => {
        const baseConfig = {
            rows: 1,
            cols: 2,
            cells: [
                {x: 0, y: 0, emoji: 'Base-left'},
                {x: 1, y: 0, emoji: 'Base-right'},
            ],
            roomOverrides: {},
            layoutOverrides: {
                phonePortrait: {
                    rows: 2,
                    cols: 1,
                    cells: [
                        {x: 0, y: 0, emoji: 'Phone-top'},
                        {x: 0, y: 1, emoji: 'Phone-bottom'},
                    ],
                    roomOverrides: {
                        Kitchen: {
                            cells: [
                                {x: 0, y: 1, emoji: 'Kitchen-bottom'},
                            ],
                        },
                    },
                },
            },
        };

        const resolved = configResolver.resolveDisplayConfig(
            baseConfig,
            'phonePortrait',
            'Kitchen'
        );

        expect(resolved.rows).to.equal(2);
        expect(resolved.cols).to.equal(1);
        expect(resolved.cells.map((cell: any) => cell.emoji)).to.deep.equal([
            'Phone-top',
            'Kitchen-bottom',
        ]);
        expect(baseConfig.layoutOverrides.phonePortrait.cells[1].emoji).to.equal(
            'Phone-bottom'
        );
    });

    it('validates every responsive layout and its room overrides', () => {
        const config = {
            rows: 1,
            cols: 1,
            cells: [{x: 0, y: 0}],
            layoutOverrides: {
                phonePortrait: {
                    rows: 2,
                    cols: 1,
                    cells: [{x: 0, y: 0}],
                    roomOverrides: {},
                },
            },
        };

        expect(() => configResolver.validateConfig(config)).to.throw(
            /missing cell at \(0,1\)/
        );
    });
});
