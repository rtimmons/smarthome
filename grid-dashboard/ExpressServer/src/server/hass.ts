import { Request as RQ, Response as RS, Router } from 'express';
import * as rpn from 'request-promise-native';

import { appConfig } from './config';

const app = Router();

const activateScene = async (req: RQ, res: RS) => {
    const scene = req.params['scene'];
    const useCoreApi =
        Boolean(process.env.SUPERVISOR_TOKEN) && !process.env.HASS_WEBHOOK_BASE;
    const sceneId = scene.replace(/^scene_/, '');
    if (!sceneId || sceneId === scene) {
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
        const response = await rpn({
            url,
            method: 'POST',
            headers: useCoreApi
                ? { Authorization: `Bearer ${process.env.SUPERVISOR_TOKEN}` }
                : undefined,
            body: useCoreApi
                ? { entity_id: `script.fast_scene_${sceneId}` }
                : undefined,
            json: useCoreApi,
            resolveWithFullResponse: true,
            simple: false,
            timeout: 10000,
        });

        if (response.statusCode >= 400) {
            res.status(response.statusCode).send(response.body || 'error');
            return;
        }

        res.send('OK');
    } catch (err) {
        const statusCode = Number(err && err.statusCode) || 502;
        res.status(statusCode).json({
            error:
                (err && err.message) || 'Failed to call Home Assistant webhook',
            scene,
        });
    }
};

app.get('/scenes/:scene', activateScene);
app.post('/scenes/:scene', activateScene);

export const hass = app;
