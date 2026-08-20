import { expect } from 'chai';

import {
    createSceneActivator,
    fastSceneEntityId,
    SCENE_WEBHOOK_TIMEOUT_MS,
    SceneActivationGate,
    type SceneActivationRuntime,
} from './hass';

class FakeResponse {
    statusCode = 200;
    body: unknown;
    headers = new Map<string, string>();

    set(name: string, value: string) {
        this.headers.set(name, value);
        return this;
    }

    status(statusCode: number) {
        this.statusCode = statusCode;
        return this;
    }

    send(body: unknown) {
        this.body = body;
        return this;
    }

    json(body: unknown) {
        this.body = body;
        return this;
    }
}

const coreRuntime = (): SceneActivationRuntime => ({
    coreApiBase: 'http://supervisor/core/api',
    webhookBase: 'http://homeassistant.local:8123/api/webhook',
    supervisorToken: 'test-token',
    useCoreApi: true,
});

describe('Home Assistant scene routing', () => {
    it('maps dashboard scene paths to fast-scene scripts', () => {
        expect(fastSceneEntityId('scene_living_room_high')).to.equal(
            'script.fast_scene_living_room_high'
        );
        expect(fastSceneEntityId('scene_all_off')).to.equal(
            'script.fast_scene_all_off'
        );
    });

    it('rejects malformed scene paths', () => {
        expect(fastSceneEntityId('living_room_high')).to.equal(undefined);
        expect(fastSceneEntityId('scene_../living_room_high')).to.equal(
            undefined
        );
        expect(fastSceneEntityId('scene_living-room-high')).to.equal(undefined);
    });

    it('coalesces duplicate scene requests inside the debounce window', () => {
        const gate = new SceneActivationGate(1000);

        expect(gate.claim('scene_all_off', 10_000)).to.equal(10_000);
        expect(gate.claim('scene_all_off', 10_038)).to.equal(undefined);
        expect(gate.claim('scene_all_off', 11_000)).to.equal(11_000);
    });

    it('accepts a retry exactly at the debounce boundary', () => {
        const gate = new SceneActivationGate(1000);

        expect(gate.claim('scene_all_off', 10_000)).to.equal(10_000);
        expect(gate.claim('scene_all_off', 10_999)).to.equal(undefined);
        expect(gate.claim('scene_all_off', 11_000)).to.equal(11_000);
    });

    it('does not coalesce different scenes and releases failed requests', () => {
        const gate = new SceneActivationGate(1000);
        const allOffClaim = gate.claim('scene_all_off', 10_000);

        expect(gate.claim('scene_kitchen_off', 10_010)).to.equal(10_010);
        expect(allOffClaim).to.equal(10_000);
        gate.release('scene_all_off', allOffClaim!);
        expect(gate.claim('scene_all_off', 10_020)).to.equal(10_020);
    });

    it('does not let an old failed claim release a newer activation', () => {
        const gate = new SceneActivationGate(1000);
        const oldClaim = gate.claim('scene_all_off', 10_000)!;
        expect(gate.claim('scene_all_off', 11_000)).to.equal(11_000);

        gate.release('scene_all_off', oldClaim);
        expect(gate.claim('scene_all_off', 11_001)).to.equal(undefined);
    });

    it('posts valid scenes to the authenticated blocking wrapper entry point', async () => {
        const requests: Array<{ url: string; options?: RequestInit }> = [];
        const activate = createSceneActivator({
            gate: new SceneActivationGate(),
            now: () => 10_000,
            runtime: coreRuntime,
            request: async (url, options) => {
                requests.push({ url, options });
                return {
                    statusCode: 200,
                    body: 'OK',
                    headers: new Headers(),
                };
            },
        });
        const response = new FakeResponse();

        await activate(
            { params: { scene: 'scene_all_off' } } as any,
            response as any
        );

        expect(response.statusCode).to.equal(200);
        expect(response.body).to.equal('OK');
        expect(response.headers.get('Cache-Control')).to.equal('no-store');
        expect(requests).to.have.length(1);
        expect(requests[0].url).to.equal(
            'http://supervisor/core/api/services/script/turn_on'
        );
        expect(requests[0].options).to.deep.include({ method: 'POST' });
        expect(requests[0].options?.headers).to.deep.equal({
            Authorization: 'Bearer test-token',
            'Content-Type': 'application/json',
        });
        expect(requests[0].options?.body).to.equal(
            JSON.stringify({ entity_id: 'script.fast_scene_all_off' })
        );
    });

    it('preserves the webhook path for standalone development', async () => {
        const requests: Array<{ url: string; options?: RequestInit }> = [];
        const webhookSignal = new AbortController().signal;
        const activate = createSceneActivator({
            gate: new SceneActivationGate(),
            runtime: () => ({
                coreApiBase: 'http://supervisor/core/api',
                webhookBase: 'http://localhost:8123/api/webhook',
                useCoreApi: false,
            }),
            webhookSignal: () => webhookSignal,
            request: async (url, options) => {
                requests.push({ url, options });
                return {
                    statusCode: 200,
                    body: 'OK',
                    headers: new Headers(),
                };
            },
        });

        await activate(
            { params: { scene: 'scene_office_medium' } } as any,
            new FakeResponse() as any
        );

        expect(requests).to.deep.equal([
            {
                url: 'http://localhost:8123/api/webhook/scene_office_medium',
                options: {
                    method: 'POST',
                    headers: undefined,
                    body: undefined,
                    signal: webhookSignal,
                },
            },
        ]);
        expect(SCENE_WEBHOOK_TIMEOUT_MS).to.equal(60_000);
    });

    it('acknowledges duplicate requests without calling Home Assistant twice', async () => {
        const requestTimes = [10_000, 10_038];
        let requestCount = 0;
        const activate = createSceneActivator({
            gate: new SceneActivationGate(),
            now: () => requestTimes.shift()!,
            runtime: coreRuntime,
            request: async () => {
                requestCount += 1;
                return {
                    statusCode: 200,
                    body: 'OK',
                    headers: new Headers(),
                };
            },
        });
        const first = new FakeResponse();
        const duplicate = new FakeResponse();
        const request = { params: { scene: 'scene_all_off' } } as any;

        await activate(request, first as any);
        await activate(request, duplicate as any);

        expect(requestCount).to.equal(1);
        expect(duplicate.statusCode).to.equal(202);
        expect(duplicate.body).to.deep.equal({
            scene: 'scene_all_off',
            deduplicated: true,
        });
        expect(duplicate.headers.get('Cache-Control')).to.equal('no-store');
    });

    it('releases failed activations so an immediate retry reaches Home Assistant', async () => {
        const requestTimes = [10_000, 10_020];
        let requestCount = 0;
        const activate = createSceneActivator({
            gate: new SceneActivationGate(),
            now: () => requestTimes.shift()!,
            runtime: coreRuntime,
            request: async () => {
                requestCount += 1;
                return {
                    statusCode: requestCount === 1 ? 503 : 200,
                    body: requestCount === 1 ? 'unavailable' : 'OK',
                    headers: new Headers(),
                };
            },
        });
        const request = { params: { scene: 'scene_kitchen_off' } } as any;
        const failed = new FakeResponse();
        const retry = new FakeResponse();

        await activate(request, failed as any);
        await activate(request, retry as any);

        expect(requestCount).to.equal(2);
        expect(failed.statusCode).to.equal(503);
        expect(retry.statusCode).to.equal(200);
        expect(retry.body).to.equal('OK');
    });

    it('returns a retryable gateway error when the Home Assistant request throws', async () => {
        const requestTimes = [10_000, 10_020];
        let requestCount = 0;
        const activate = createSceneActivator({
            gate: new SceneActivationGate(),
            now: () => requestTimes.shift()!,
            runtime: coreRuntime,
            request: async () => {
                requestCount += 1;
                if (requestCount === 1) {
                    throw new Error('connection reset');
                }
                return {
                    statusCode: 200,
                    body: 'OK',
                    headers: new Headers(),
                };
            },
        });
        const request = { params: { scene: 'scene_kitchen_high' } } as any;
        const failed = new FakeResponse();
        const retry = new FakeResponse();

        await activate(request, failed as any);
        await activate(request, retry as any);

        expect(requestCount).to.equal(2);
        expect(failed.statusCode).to.equal(502);
        expect(failed.body).to.deep.equal({
            error: 'connection reset',
            scene: 'scene_kitchen_high',
        });
        expect(retry.statusCode).to.equal(200);
    });

    it('rejects malformed scene routes before making an upstream request', async () => {
        let requestCount = 0;
        const activate = createSceneActivator({
            gate: new SceneActivationGate(),
            runtime: coreRuntime,
            request: async () => {
                requestCount += 1;
                throw new Error('should not be called');
            },
        });
        const response = new FakeResponse();

        await activate(
            { params: { scene: 'scene_../all_off' } } as any,
            response as any
        );

        expect(requestCount).to.equal(0);
        expect(response.statusCode).to.equal(400);
        expect(response.body).to.equal('Invalid scene');
    });
});
