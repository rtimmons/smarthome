import { expect } from 'chai';

const configResolver: any = require('./config-resolver');

describe('ConfigResolver', () => {
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
});
