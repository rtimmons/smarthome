import { Request as RQ, Response as RS, Router } from 'express';

import { appConfig } from './config';
import { requestText } from './http';

const app = Router();

export const fastSceneEntityId = (scene: string): string | undefined => {
    const match = /^scene_([a-z0-9]+(?:_[a-z0-9]+)*)$/.exec(scene);
    return match ? `script.fast_scene_${match[1]}` : undefined;
};

const activateScene = async (req: RQ, res: RS) => {
    const sceneParam = req.params['scene'];
    const scene = Array.isArray(sceneParam) ? sceneParam[0] : sceneParam;
    if (!scene) {
        res.status(400).send('Invalid scene');
        return;
    }
    const useCoreApi =
        Boolean(process.env.SUPERVISOR_TOKEN) && !process.env.HASS_WEBHOOK_BASE;
    const entityId = fastSceneEntityId(scene);
    if (!entityId) {
        res.status(400).send('Invalid scene');
        return;
    }

    // The authenticated Core API avoids webhook local-network filtering while
    // retaining HASS_WEBHOOK_BASE support for standalone local development.
    const url = useCoreApi
        ? `${appConfig.coreApiBase}/services/script/turn_on`
        : `${appConfig.webhookBase}/${scene}`;
    console.log({ url });

    // GET remains supported for legacy in-house IoT callers. Prevent caches from
    // swallowing repeated activations; new dashboard clients should use POST.
    res.set('Cache-Control', 'no-store');

    try {
        const response = await requestText(url, {
            method: 'POST',
            headers: useCoreApi
                ? {
                      Authorization: `Bearer ${process.env.SUPERVISOR_TOKEN}`,
                      'Content-Type': 'application/json',
                  }
                : undefined,
            body: useCoreApi
                ? JSON.stringify({ entity_id: entityId })
                : undefined,
        });

        if (response.statusCode >= 400) {
            res.status(response.statusCode).send(response.body || 'error');
            return;
        }

        res.send('OK');
    } catch (err) {
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

app.get('/scenes/:scene', activateScene);
app.post('/scenes/:scene', activateScene);

export const hass = app;
