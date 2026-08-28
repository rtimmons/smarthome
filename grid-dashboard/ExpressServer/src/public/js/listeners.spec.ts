import { expect } from 'chai';

const listeners: any = require('./listeners');

describe('listeners banner formatting', () => {
    it('does not clear zone toggle cells on room change', () => {
        const activeCells = new listeners.ActiveCells();
        const roomSelector = {
            config: {
                activeWhenRoom: 'Kitchen',
            },
            isActiveForRoom: (room: string) => room === 'Kitchen',
            setActiveCalls: [] as boolean[],
            setActive(value: boolean) {
                this.setActiveCalls.push(value);
            },
        };
        const zoneToggle = {
            config: {
                togglesRoom: 'Kitchen',
            },
            isActiveForRoom: () => false,
            setActiveCalls: [] as boolean[],
            setActive(value: boolean) {
                this.setActiveCalls.push(value);
            },
        };

        activeCells.onMessage({
            Event: {
                ToRoom: 'Kitchen',
            },
            Globals: {
                App: {
                    eachCell: (fn: (cell: unknown) => void) => {
                        [roomSelector, zoneToggle].forEach(fn);
                    },
                },
            },
        });

        expect(roomSelector.setActiveCalls).to.deep.equal([true]);
        expect(zoneToggle.setActiveCalls).to.deep.equal([]);
    });

    it('formats standard tracks with em dash separator', () => {
        const banner = listeners.formatBannerText({
            title: 'Teardrop',
            artist: 'Massive Attack',
            stationName: '',
        });

        expect(banner).to.equal('Teardrop — Massive Attack');
    });

    it('parses SiriusXM metadata embedded in the title', () => {
        const banner = listeners.formatBannerText({
            title:
                "TYPE=SNG|TITLE Immortal (Steve Aoki Remix)|ARTIST 2LOT|ALBUM HiROQUEST 3: Paragon Remixed — CH 735 - Steve Aoki's Remix Radio",
            artist: '',
            stationName: "CH 735 - Steve Aoki's Remix Radio",
        });

        expect(banner).to.equal('Immortal (Steve Aoki Remix) - 2LOT');
    });

    it('falls back to the station name when artist is unavailable', () => {
        const banner = listeners.formatBannerText({
            title: 'Morning Edition',
            artist: '',
            stationName: 'NPR',
        });

        expect(banner).to.equal('Morning Edition — NPR');
    });

    it('prefers the active intent banner over recent intent', () => {
        const banner = listeners.intentBannerText({
            activeIntent: {
                message: 'Joining all to Kitchen (2/8)',
            },
            recentIntent: {
                message: 'Joined all to Bedroom (8/8)',
            },
        });

        expect(banner).to.equal('Joining all to Kitchen (2/8)');
    });

    it('flags timed out intents as errors', () => {
        const hasError = listeners.intentHasError({
            recentIntent: {
                status: 'timed_out',
                message: 'Join-all to Kitchen timed out',
            },
        });

        expect(hasError).to.equal(true);
    });

    it('uses observed zones instead of lagging join-all progress', () => {
        const status = listeners.reconcileIntentStatus(
            {
                activeIntent: {
                    status: 'running',
                    targetRoom: 'Kitchen',
                    roomNames: ['Kitchen', 'Bedroom', 'Office'],
                    joinedRooms: ['Kitchen'],
                    missingRooms: ['Bedroom', 'Office'],
                    message: 'Joining all to Kitchen (1/3 joined; awaiting 2)',
                },
                recentIntent: null,
            },
            [
                { members: ['Kitchen', 'Bedroom', 'Office'] },
            ]
        );

        expect(status.activeIntent.joinedRooms).to.deep.equal([
            'Kitchen',
            'Bedroom',
            'Office',
        ]);
        expect(status.activeIntent.missingRooms).to.deep.equal([]);
        expect(status.activeIntent.observedComplete).to.equal(true);
        expect(status.activeIntent.message).to.equal(
            'Joined all to Kitchen (3/3)'
        );
    });

    it('does not show a timeout error after topology was observed complete', () => {
        const status = listeners.reconcileIntentStatus(
            {
                activeIntent: null,
                recentIntent: {
                    status: 'timed_out',
                    targetRoom: 'Kitchen',
                    roomNames: ['Kitchen', 'Bedroom'],
                    missingRooms: ['Bedroom'],
                    message: 'Join-all to Kitchen timed out',
                },
            },
            [{ members: ['Kitchen', 'Bedroom'] }]
        );

        expect(listeners.intentHasError(status)).to.equal(false);
        expect(listeners.intentBannerText(status)).to.equal(
            'Joined all to Kitchen (2/2)'
        );
    });

    it('recognizes observed manual join and leave outcomes', () => {
        const zones = [
            { members: ['Kitchen'] },
            { members: ['Bedroom', 'Office'] },
        ];

        expect(
            listeners.zoneMutationSatisfied(
                {
                    room: 'Office',
                    anchorRoom: 'Bedroom',
                    desiredJoined: true,
                },
                zones
            )
        ).to.equal(true);
        expect(
            listeners.zoneMutationSatisfied(
                {
                    room: 'Office',
                    anchorRoom: 'Kitchen',
                    desiredJoined: false,
                },
                zones
            )
        ).to.equal(true);
        expect(
            listeners.zoneMutationSatisfied(
                {
                    room: 'Kitchen',
                    anchorRoom: 'Kitchen',
                    desiredJoined: false,
                },
                zones
            )
        ).to.equal(true);
    });

    it('clears intent banner when no active or recent intent exists', () => {
        const banner = listeners.intentBannerText({
            activeIntent: null,
            recentIntent: null,
        });

        expect(banner).to.equal('');
    });
});
