import { Request as RQ, Response as RS, Router } from 'express';
import * as rpn from 'request-promise-native';

import { appConfig } from './config';

const app = Router();

app.get('/scenes/:scene', async (req: RQ, res: RS) => {
    const scene = req.params['scene'];
    const url = `${appConfig.webhookBase}/${scene}`;
    console.log({ url });
    await rpn({
        url,
        method: 'post',
        headers: appConfig.webhookBase.includes('supervisor')
            ? { Authorization: `Bearer ${process.env.SUPERVISOR_TOKEN}` }
            : undefined,
    });
    return res.send('OK');
});

export const hass = app;
