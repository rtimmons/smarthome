import {expect} from 'chai';

const {MusicController}: any = require('./music-controller');

class FakeRequest {
    doneCallbacks: Array<(...args: any[]) => void> = [];
    failCallbacks: Array<(...args: any[]) => void> = [];

    done(callback: (...args: any[]) => void) {
        this.doneCallbacks.push(callback);
        return this;
    }

    fail(callback: (...args: any[]) => void) {
        this.failCallbacks.push(callback);
        return this;
    }

    resolve(...args: any[]) {
        this.doneCallbacks.forEach(callback => callback(...args));
    }

    reject(...args: any[]) {
        this.failCallbacks.forEach(callback => callback(...args));
    }
}

const controllerFixture = () => {
    const requests: Array<{value: unknown; request: FakeRequest}> = [];
    const events: Array<{topic: string; event: any}> = [];
    const accepted: Array<{generation: number; response: unknown}> = [];
    const failed: Array<{generation: number; message: string}> = [];
    const statuses: any[] = [];
    const app = {
        config: {rooms: ['Living Room', 'Kitchen']},
        currentRoom: () => 'Living Room',
        acceptTopologyOperation: (generation: number, response: unknown) => {
            accepted.push({generation, response});
            return (response as any)?.operation || (response as any)?.intent || null;
        },
        failTopologyOperation: (generation: number, message: string) => {
            failed.push({generation, message});
        },
        updateIntentStatus: (status: any) => statuses.push(status),
    };
    const requester = {
        request(value: unknown) {
            const request = new FakeRequest();
            requests.push({value, request});
            return request;
        },
    };
    const controller = new MusicController({
        requester,
        root: '',
        app,
        pubsub: {
            submit(topic: string, event: any) {
                events.push({topic, event});
            },
        },
    });
    return {accepted, controller, events, failed, requests, statuses};
};

describe('MusicController Sonos state', () => {
    beforeEach(() => {
        (globalThis as any).window = {
            location: {pathname: '/api/hassio_ingress/token/'},
        };
    });

    afterEach(() => {
        delete (globalThis as any).window;
    });

    it('builds ingress-relative URLs with encoded path segments', () => {
        const fixture = controllerFixture();

        fixture.controller.volumeUp();
        fixture.controller.favorite("735 - Steve Aoki's Remix Radio");

        expect(fixture.requests.map(request => request.value)).to.deep.equal([
            '/api/hassio_ingress/token/sonos/Living%20Room/groupVolume/%2B2',
            "/api/hassio_ingress/token/sonos/Living%20Room/favorite/735%20-%20Steve%20Aoki's%20Remix%20Radio",
        ]);
    });

    it('keeps a live zones response usable while naming unavailable portable rooms', () => {
        const fixture = controllerFixture();
        const headers: {[name: string]: string} = {
            'X-Sonos-Age-Ms': '0',
            'X-Sonos-Response-Source': 'home_assistant',
            'X-Sonos-Response-Stale': 'false',
            'X-Sonos-Unavailable-Rooms': 'Move',
        };

        expect(fixture.controller.responseMeta({
            getResponseHeader: (name: string) => headers[name] || null,
        })).to.deep.equal({
            source: 'home_assistant',
            unknown: false,
            stale: false,
            observedAt: '',
            ageMs: 0,
            unavailableRooms: ['Move'],
        });
    });

    it('publishes unknown media and topology after request failures', () => {
        const fixture = controllerFixture();

        fixture.controller.fetchState();
        fixture.requests[0].request.reject({status: 503});
        fixture.requests[1].request.reject({status: 503});

        expect(fixture.events.slice(0, 2)).to.deep.equal([
            {
                topic: 'Room.StateObserved',
                event: {
                    State: null,
                    Meta: {unknown: true, statusCode: 503},
                    RequestSequence: 1,
                },
            },
            {
                topic: 'Room.ZonesObserved',
                event: {
                    Zones: null,
                    Meta: {unknown: true, statusCode: 503},
                    RequestSequence: 1,
                },
            },
        ]);
    });

    it('rejects an older response while a newer request is still pending', () => {
        const fixture = controllerFixture();

        fixture.controller.fetchState();
        fixture.controller.fetchState();
        fixture.requests[0].request.resolve({currentTrack: {title: 'old'}});
        fixture.requests[1].request.resolve([{members: [{roomName: 'old'}]}]);
        fixture.requests[2].request.resolve({activeIntent: {id: 'old'}});
        expect(fixture.events).to.deep.equal([]);

        fixture.requests[3].request.resolve({currentTrack: {title: 'new'}});
        fixture.requests[4].request.resolve([{members: [{roomName: 'new'}]}]);
        fixture.requests[5].request.resolve({activeIntent: {id: 'new'}});

        expect(fixture.events.map(item => [item.topic, item.event.RequestSequence]))
            .to.deep.equal([
                ['Room.StateObserved', 2],
                ['Room.ZonesObserved', 2],
                ['Intent.StateObserved', 2],
            ]);
    });

    it('associates manual topology responses and failures with their generation', () => {
        const fixture = controllerFixture();

        fixture.controller.joinRoom('Guest Bathroom', 'Living Room', 7);
        fixture.requests[0].request.resolve({operation: {id: 'operation-7'}});
        fixture.controller.leaveRoom('Guest Bathroom', 8);
        fixture.requests[1].request.reject({
            responseJSON: {error: 'speaker unavailable'},
        });

        expect(fixture.accepted).to.deep.equal([
            {generation: 7, response: {operation: {id: 'operation-7'}}},
        ]);
        expect(fixture.failed).to.deep.equal([
            {generation: 8, message: 'speaker unavailable'},
        ]);
    });

    it('associates a preset response and publishes its pending operation', () => {
        const fixture = controllerFixture();

        fixture.controller.preset('$room-tv', 9);
        fixture.requests[0].request.resolve({
            operation: {id: 'preset-operation', status: 'running'},
        });

        expect(fixture.requests[0].value).to.equal(
            '/api/hassio_ingress/token/sonos/Living%20Room/preset/Living%20Room-tv'
        );
        expect(fixture.accepted).to.deep.equal([
            {
                generation: 9,
                response: {
                    operation: {id: 'preset-operation', status: 'running'},
                },
            },
        ]);
        expect(fixture.statuses[0].activeIntent).to.deep.equal({
            id: 'preset-operation',
            status: 'running',
        });
        expect(fixture.statuses[0].recentIntent).to.equal(null);
    });
});
