import { expect } from 'chai';

const listeners: any = require('./listeners');

describe('listeners banner formatting', () => {
    it('distinguishes live, stale, and unknown response metadata', () => {
        expect(listeners.freshnessFromMeta({})).to.equal('live');
        expect(listeners.freshnessFromMeta({stale: true})).to.equal('stale');
        expect(
            listeners.freshnessFromMeta({stale: true, unknown: true})
        ).to.equal('unknown');
    });

    it('retains known zones while stale and marks only missing state unknown', () => {
        const updater = new listeners.ZoneUpdater();
        const calls: Array<string | string[][]> = [];
        const app = {
            setZonesStale: (_meta: unknown, zones: Array<{members: string[]}>) => {
                calls.push('stale');
                calls.push(zones.map(zone => zone.members));
            },
            setZonesUnknown: () => calls.push('unknown'),
            updateZones: () => calls.push('live'),
        };

        updater.onMessage({
            Event: {
                Zones: [{members: [{roomName: 'Kitchen'}]}],
                Meta: {stale: true, ageMs: 2_000},
                RequestSequence: 1,
            },
            Globals: {App: app},
        });
        updater.onMessage({
            Event: {
                Zones: null,
                Meta: {unknown: true},
                RequestSequence: 2,
            },
            Globals: {App: app},
        });

        expect(calls).to.deep.equal(['stale', [['Kitchen']], 'unknown']);
    });

    it('ignores an older zones response that arrives after a newer one', () => {
        const updater = new listeners.ZoneUpdater();
        const updates: string[][] = [];
        const app = {
            setZonesStale: () => undefined,
            setZonesUnknown: () => undefined,
            updateZones: (zones: Array<{members: string[]}>) =>
                updates.push(zones[0].members),
        };

        updater.onMessage({
            Event: {
                Zones: [{members: [{roomName: 'Kitchen'}]}],
                Meta: {},
                RequestSequence: 2,
            },
            Globals: {App: app},
        });
        updater.onMessage({
            Event: {
                Zones: [{members: [{roomName: 'Bedroom'}]}],
                Meta: {},
                RequestSequence: 1,
            },
            Globals: {App: app},
        });

        expect(updates).to.deep.equal([['Kitchen']]);
    });

    it('passes an unavailable portable-room marker through with live zones', () => {
        const updater = new listeners.ZoneUpdater();
        let observedMeta: any = null;
        updater.onMessage({
            Event: {
                Zones: [{members: [{roomName: 'Kitchen'}]}],
                Meta: {unavailableRooms: ['Move']},
                RequestSequence: 1,
            },
            Globals: {App: {
                updateZones: (_zones: unknown, meta: unknown) => { observedMeta = meta; },
            }},
        });

        expect(observedMeta).to.deep.equal({unavailableRooms: ['Move']});
    });

    it('keeps stale artwork but clears it when media state becomes unknown', () => {
        const changer = new listeners.BackgroundChanger();
        const calls: Array<[string, unknown]> = [];
        const app = {
            setSonosMediaFreshness: (value: string) =>
                calls.push(['freshness', value]),
            setBackgroundImage: (value: string) =>
                calls.push(['art', value]),
            setTrackBanner: (value: string) => calls.push(['track', value]),
        };

        changer.onMessage({
            Event: {
                State: {
                    currentTrack: {
                        title: 'Teardrop',
                        artist: 'Massive Attack',
                        absoluteAlbumArtUri: './sonos/Kitchen/artwork',
                    },
                },
                Meta: {stale: true, ageMs: 3_000},
                RequestSequence: 1,
            },
            Globals: {App: app},
        });
        changer.onMessage({
            Event: {
                State: null,
                Meta: {unknown: true},
                RequestSequence: 2,
            },
            Globals: {App: app},
        });

        expect(calls).to.deep.equal([
            ['freshness', 'stale'],
            ['art', './sonos/Kitchen/artwork'],
            ['track', 'Teardrop — Massive Attack (stale 3s)'],
            ['freshness', 'unknown'],
            ['art', ''],
            ['track', ''],
        ]);
    });

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
                'TYPE=SNG|TITLE Synthetic Track|ARTIST Test Artist|ALBUM Fixture Album — CH 999 - Test Radio',
            artist: '',
            stationName: 'CH 999 - Test Radio',
        });

        expect(banner).to.equal('Synthetic Track - Test Artist');
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
