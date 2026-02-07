import { Request as RQ, Response as RS, Router } from 'express';
import * as rpn from 'request-promise-native';

import { appConfig } from './config';

const app = Router();

app.get('/scenes/:scene', async (req: RQ, res: RS) => {
    const scene = req.params['scene'];
    const url = `${appConfig.webhookBase}/${scene}`;
    console.log({ url });

    try {
        const response = await rpn({
            url,
            method: 'POST',
            headers: appConfig.webhookBase.includes('supervisor')
                ? { Authorization: `Bearer ${process.env.SUPERVISOR_TOKEN}` }
                : undefined,
            resolveWithFullResponse: true,
            simple: false,
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
});

export const hass = app;
