import { Request as RQ, Response as RS, Router } from 'express';

import { appConfig } from './config';
import { requestText, type HttpResponse } from './http';

const app = Router();

const THERMOSTAT_ENTITIES: Readonly<Record<string, string>> = {
    Bedroom: 'climate.bedroom',
    Kitchen: 'climate.kitchen',
    'Living Room': 'climate.living_room',
    Move: 'weather.forecast_home',
    Office: 'climate.office',
};

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

export const thermostatEntityId = (room: string): string | undefined =>
    THERMOSTAT_ENTITIES[room];

export interface ThermostatStateReaderDependencies {
    request?: (
        url: string,
        options?: RequestInit
    ) => Promise<HttpResponse>;
    runtime?: () => SceneActivationRuntime;
}

const optionalNumber = (value: unknown): number | null => {
    if (value === undefined || value === null || value === '') {
        return null;
    }
    const parsed = typeof value === 'number' ? value : Number(value);
    return Number.isFinite(parsed) ? parsed : null;
};

export const createThermostatStateReader = (
    dependencies: ThermostatStateReaderDependencies = {}
) => {
    const request = dependencies.request ?? requestText;
    const runtime = dependencies.runtime ?? defaultRuntime;

    return async (req: RQ, res: RS) => {
        const roomParam = req.params['room'];
        const room = Array.isArray(roomParam) ? roomParam[0] : roomParam;
        if (!room) {
            res.status(400).send('Invalid room');
            return;
        }

        res.set('Cache-Control', 'no-store');
        const entityId = thermostatEntityId(room);
        if (!entityId) {
            res.json({ room, thermostat: null });
            return;
        }

        const stateRuntime = runtime();
        if (!stateRuntime.supervisorToken) {
            res.status(503).json({
                error: 'Home Assistant API is unavailable',
                room,
            });
            return;
        }

        try {
            const response = await request(
                `${stateRuntime.coreApiBase}/states/${encodeURIComponent(entityId)}`,
                {
                    headers: {
                        Authorization: `Bearer ${stateRuntime.supervisorToken}`,
                    },
                }
            );

            if (response.statusCode >= 400) {
                res.status(response.statusCode).json({
                    error: 'Unable to read thermostat state',
                    room,
                });
                return;
            }

            let state: any;
            try {
                state = JSON.parse(response.body);
            } catch (_err) {
                res.status(502).json({
                    error: 'Invalid thermostat state response',
                    room,
                });
                return;
            }

            const attributes = state && state.attributes;
            if (!attributes || typeof attributes !== 'object') {
                res.status(502).json({
                    error: 'Invalid thermostat state response',
                    room,
                });
                return;
            }

            const isWeatherEntity = entityId.startsWith('weather.');

            res.json({
                room,
                thermostat: {
                    entityId,
                    currentTemperature: optionalNumber(
                        isWeatherEntity
                            ? attributes.temperature
                            : attributes.current_temperature
                    ),
                    targetTemperature: isWeatherEntity
                        ? null
                        : optionalNumber(attributes.temperature),
                    temperatureUnit:
                        typeof attributes.temperature_unit === 'string'
                            ? attributes.temperature_unit
                            : null,
                    hvacMode:
                        !isWeatherEntity && typeof state.state === 'string'
                            ? state.state
                            : null,
                },
            });
        } catch (err) {
            const message =
                err instanceof Error
                    ? err.message
                    : 'Unable to read thermostat state';
            res.status(502).json({ error: message, room });
        }
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
const readThermostatState = createThermostatStateReader();

app.get('/scenes/:scene', activateScene);
app.post('/scenes/:scene', activateScene);
app.get('/thermostats/:room', readThermostatState);

export const hass = app;
