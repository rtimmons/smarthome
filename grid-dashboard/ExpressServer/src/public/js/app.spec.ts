import {expect} from 'chai';
import {readFileSync} from 'fs';
import {createContext, runInContext} from 'vm';

const loadAppModule = (): any => {
    const context: any = createContext({
        console,
        module: {exports: {}},
    });
    runInContext(
        readFileSync(require.resolve('./sonos-operation-state.js'), 'utf8'),
        context
    );
    context.module = {exports: {}};
    runInContext(readFileSync(require.resolve('./app.js'), 'utf8'), context);
    return context.module.exports;
};

const {App, bannerTrackIsCurrent} = loadAppModule();
const {SonosOperationGate}: any = require('./sonos-operation-state');

describe('App banner lifecycle', () => {
    it('reuses only a banner track still attached to the current grid cell', () => {
        const currentTrack = {};
        const detachedTrack = {};
        const bannerContent = {
            0: {contains: (candidate: unknown) => candidate === currentTrack},
            length: 1,
        };

        expect(
            bannerTrackIsCurrent(bannerContent, {0: currentTrack, length: 1})
        ).to.equal(true);
        expect(
            bannerTrackIsCurrent(bannerContent, {0: detachedTrack, length: 1})
        ).to.equal(false);
    });
});

describe('App Sonos topology pending lifecycle', () => {
    it('keeps reachable zones live while warning about an unavailable portable room', () => {
        const app: any = Object.create(App.prototype);
        app.room = 'Kitchen';
        app.rooms = ['Kitchen', 'Move'];
        app.pendingZoneMutations = {};
        app.grid = {
            updateZones: () => undefined,
            setZonesStale: () => undefined,
        };
        app.setZonesUnknown = () => undefined;
        app._reconcileZoneMutations = () => undefined;
        app._refreshIntentPresentation = () => undefined;

        app.updateZones([{members: ['Kitchen']}], {unavailableRooms: ['Move']});

        expect(app.zoneStateFreshness).to.equal('live');
        expect(app.topologyBanner).to.equal('Sonos unavailable: Move');
    });

    it('adopts a last-confirmed stale zones payload on a fresh page', () => {
        const zoneUpdates: unknown[] = [];
        const app: any = Object.create(App.prototype);
        app.room = 'Kitchen';
        app.rooms = ['Kitchen', 'Bedroom'];
        app.knownZones = null;
        app.pendingZoneMutations = {};
        app.grid = {
            updateZones: (value: unknown) => zoneUpdates.push(value),
            setZonesStale: () => undefined,
        };
        app._reconcileZoneMutations = () => undefined;
        app._refreshIntentPresentation = () => undefined;
        app._refreshBanner = () => undefined;

        const staleZones = [{members: ['Kitchen']}];
        app.setZonesStale({ageMs: 2_000}, staleZones);

        expect(app.knownZones).to.deep.equal(staleZones);
        expect(app.zoneStateFreshness).to.equal('stale');
        expect(zoneUpdates).to.deep.equal([{
            on: ['Kitchen'],
            off: ['Bedroom'],
        }]);
    });

    it('blocks presets while stale or unknown and correlates a live preset', () => {
        ['stale', 'unknown'].forEach(freshness => {
            let requests = 0;
            const app: any = Object.create(App.prototype);
            app.zoneStateFreshness = freshness;
            app.musicController = {preset: () => requests++};
            app.setIntentBanner = () => undefined;

            app.onAction('Music.Preset', ['Office-tv'], {
                Submitted: new Date(),
            });
            expect(requests).to.equal(0);
        });

        const calls: Array<[string, number]> = [];
        const app: any = Object.create(App.prototype);
        app.zoneStateFreshness = 'live';
        app.beginTopologyOperation = () => 12;
        app.musicController = {
            preset: (name: string, generation: number) =>
                calls.push([name, generation]),
        };

        app.onAction('Music.Preset', ['Office-tv'], {
            Submitted: new Date(),
        });
        expect(calls).to.deep.equal([['Office-tv', 12]]);
    });

    it('ignores a late preset response after a newer operation begins', () => {
        const app: any = Object.create(App.prototype);
        app.topologyOperationGate = new SonosOperationGate();
        app.pendingZoneMutations = {};
        app.grid = {
            updateIntent: () => undefined,
            setZoneMutationPending: () => undefined,
        };
        app.setIntentBanner = () => undefined;

        const oldGeneration = app.beginTopologyOperation();
        const newGeneration = app.beginTopologyOperation();

        expect(
            app.acceptTopologyOperation(oldGeneration, {
                operation: {id: 'old-preset', status: 'running'},
            })
        ).to.equal(null);
        expect(
            app.acceptTopologyOperation(newGeneration, {
                operation: {id: 'new-operation', status: 'running'},
            }).id
        ).to.equal('new-operation');
        expect(app.topologyOperationGate.operationId).to.equal('new-operation');
    });

    it('clears the prior pending control when a new operation supersedes it', () => {
        const pendingCalls: Array<[string, boolean]> = [];
        const app: any = Object.create(App.prototype);
        app.pendingZoneMutations = {
            Bedroom: {operationGeneration: 1, timeoutHandle: 9},
        };
        app.topologyOperationGate = {begin: () => 2};
        app.window = {clearTimeout: () => undefined};
        app.grid = {
            updateIntent: () => undefined,
            setZoneMutationPending: (room: string, enabled: boolean) =>
                pendingCalls.push([room, enabled]),
        };
        app.setIntentBanner = () => undefined;

        expect(app.beginTopologyOperation()).to.equal(2);
        expect(app.pendingZoneMutations).to.deep.equal({});
        expect(pendingCalls).to.deep.equal([['Bedroom', false]]);
    });

    it('blocks every topology tap while stale or unknown', () => {
        ['stale', 'unknown'].forEach(freshness => {
            let requests = 0;
            const app: any = Object.create(App.prototype);
            app.zoneStateFreshness = freshness;
            app.pendingZoneMutations = {};
            app.musicController = {
                joinRoom: () => requests++,
                leaveRoom: () => requests++,
            };
            app.setIntentBanner = () => undefined;

            expect(
                app._toggleRoomMembership('Bedroom', {isActive: () => false})
            ).to.equal(false);
            expect(requests).to.equal(0);
        });
    });

    it('keeps a duplicate tap pending through 49,999ms and releases at 50,000ms', () => {
        let now = 0;
        let generation = 0;
        const joinCalls: string[] = [];
        const pendingCalls: Array<[string, boolean]> = [];
        const app: any = Object.create(App.prototype);
        app.now = () => now;
        app.room = 'Kitchen';
        app.zoneStateFreshness = 'live';
        app.pendingZoneMutations = {};
        app.zoneMutationTimeoutMs = 50_000;
        app.beginTopologyOperation = () => ++generation;
        app.musicController = {
            joinRoom: (room: string) => joinCalls.push(room),
            leaveRoom: () => undefined,
        };
        app.grid = {
            setZoneMutationPending: (room: string, enabled: boolean) =>
                pendingCalls.push([room, enabled]),
        };
        app.window = {
            setTimeout: () => 1,
            clearTimeout: () => undefined,
        };
        app.setIntentBanner = () => undefined;
        const cell = {isActive: () => false};

        expect(app._toggleRoomMembership('Bedroom', cell)).to.equal(true);
        now = 49_999;
        expect(app._toggleRoomMembership('Bedroom', cell)).to.equal(undefined);
        expect(joinCalls).to.deep.equal(['Bedroom']);

        now = 50_000;
        expect(app._toggleRoomMembership('Bedroom', cell)).to.equal(true);
        expect(joinCalls).to.deep.equal(['Bedroom', 'Bedroom']);
        expect(pendingCalls).to.deep.equal([
            ['Bedroom', true],
            ['Bedroom', false],
            ['Bedroom', true],
        ]);
    });

    it('clears only the matching operation for every terminal status', () => {
        const terminalStatuses = [
            'completed',
            'partial',
            'partially_completed',
            'partial_success',
            'failed',
            'timed_out',
            'cancelled',
            'superseded',
        ];

        terminalStatuses.forEach(status => {
            const app: any = Object.create(App.prototype);
            app.pendingZoneMutations = {
                Bedroom: {operationId: 'matching', timeoutHandle: 1},
                Office: {operationId: 'unrelated', timeoutHandle: 2},
            };
            app.window = {clearTimeout: () => undefined};
            app.grid = {setZoneMutationPending: () => undefined};

            app._reconcilePendingOperationStatus({
                activeIntent: null,
                recentIntent: {id: 'matching', status},
            });

            expect(app.pendingZoneMutations.Bedroom).to.equal(undefined);
            expect(app.pendingZoneMutations.Office.operationId).to.equal(
                'unrelated'
            );
        });
    });

    it('associates a manual response ID before accepting terminal status', () => {
        const app: any = Object.create(App.prototype);
        app.pendingZoneMutations = {
            Bedroom: {
                operationGeneration: 7,
                operationId: null,
                timeoutHandle: 1,
            },
        };
        app.topologyOperationGate = {
            acceptResponse: () => ({id: 'operation-7', status: 'running'}),
        };
        app.window = {clearTimeout: () => undefined};
        app.grid = {setZoneMutationPending: () => undefined};

        const operation = app.acceptTopologyOperation(7, {});

        expect(operation.id).to.equal('operation-7');
        expect(app.pendingZoneMutations.Bedroom.operationId).to.equal(
            'operation-7'
        );
    });
});
