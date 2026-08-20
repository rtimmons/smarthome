import { Request as RQ, Response as RS, Router } from 'express';

import { appConfig } from './config';
import { requestText, type HttpResponse } from './http';

const app = Router();

export const SCENE_DEDUP_WINDOW_MS = 1000;
export const SCENE_WEBHOOK_TIMEOUT_MS = 60000;

export class SceneActivationGate {
    private readonly claimedAt = new Map<string, number>();

    constructor(private readonly windowMs = SCENE_DEDUP_WINDOW_MS) {}

    claim(scene: string, now = Date.now()): number | undefined {
        const previous = this.claimedAt.get(scene);
        if (previous !== undefined && now - previous < this.windowMs) {
            return undefined;
        }
        this.claimedAt.set(scene, now);
        return now;
    }

    release(scene: string, claim: number): void {
        if (this.claimedAt.get(scene) === claim) {
            this.claimedAt.delete(scene);
        }
    }
}

const sceneActivationGate = new SceneActivationGate();

export const fastSceneEntityId = (scene: string): string | undefined => {
    const match = /^scene_([a-z0-9]+(?:_[a-z0-9]+)*)$/.exec(scene);
    return match ? `script.fast_scene_${match[1]}` : undefined;
};

export interface SceneActivationRuntime {
    coreApiBase: string;
    webhookBase: string;
    supervisorToken?: string;
    useCoreApi: boolean;
}

export interface SceneActivatorDependencies {
    gate?: SceneActivationGate;
    now?: () => number;
    request?: (
        url: string,
        options?: RequestInit
    ) => Promise<HttpResponse>;
    runtime?: () => SceneActivationRuntime;
    webhookSignal?: () => AbortSignal;
}

const defaultRuntime = (): SceneActivationRuntime => {
    const supervisorToken = process.env.SUPERVISOR_TOKEN;
    return {
        coreApiBase: appConfig.coreApiBase,
        webhookBase: appConfig.webhookBase,
        supervisorToken,
        useCoreApi:
            Boolean(supervisorToken) && !process.env.HASS_WEBHOOK_BASE,
    };
};

export const createSceneActivator = (
    dependencies: SceneActivatorDependencies = {}
) => {
    const gate = dependencies.gate ?? sceneActivationGate;
    const now = dependencies.now ?? Date.now;
    const request = dependencies.request ?? requestText;
    const runtime = dependencies.runtime ?? defaultRuntime;
    const webhookSignal =
        dependencies.webhookSignal ??
        (() => AbortSignal.timeout(SCENE_WEBHOOK_TIMEOUT_MS));

    return async (req: RQ, res: RS) => {
        const sceneParam = req.params['scene'];
        const scene = Array.isArray(sceneParam) ? sceneParam[0] : sceneParam;
        if (!scene) {
            res.status(400).send('Invalid scene');
            return;
        }
        const entityId = fastSceneEntityId(scene);
        if (!entityId) {
            res.status(400).send('Invalid scene');
            return;
        }

        // GET remains supported for legacy in-house IoT callers. Prevent caches from
        // swallowing either real activations or deduplicated acknowledgements.
        res.set('Cache-Control', 'no-store');

        const activationClaim = gate.claim(scene, now());
        if (activationClaim === undefined) {
            res.status(202).json({ scene, deduplicated: true });
            return;
        }

        // The authenticated Core API avoids webhook local-network filtering while
        // retaining HASS_WEBHOOK_BASE support for standalone local development.
        const activationRuntime = runtime();
        const url = activationRuntime.useCoreApi
            ? `${activationRuntime.coreApiBase}/services/script/turn_on`
            : `${activationRuntime.webhookBase}/${scene}`;
        console.log({ url });

        try {
            const response = await request(url, {
                method: 'POST',
                headers: activationRuntime.useCoreApi
                    ? {
                          Authorization: `Bearer ${activationRuntime.supervisorToken}`,
                          'Content-Type': 'application/json',
                      }
                    : undefined,
                body: activationRuntime.useCoreApi
                    ? JSON.stringify({ entity_id: entityId })
                    : undefined,
                ...(activationRuntime.useCoreApi
                    ? {}
                    : { signal: webhookSignal() }),
            });

            if (response.statusCode >= 400) {
                gate.release(scene, activationClaim);
                res.status(response.statusCode).send(response.body || 'error');
                return;
            }

            res.send('OK');
        } catch (err) {
            gate.release(scene, activationClaim);
            const message =
                err instanceof Error
                    ? err.message
                    : 'Failed to call Home Assistant webhook';
            res.status(502).json({
                error: message,
                scene,
            });
        }
    };
};

const activateScene = createSceneActivator();

app.get('/scenes/:scene', activateScene);
app.post('/scenes/:scene', activateScene);

export const hass = app;
