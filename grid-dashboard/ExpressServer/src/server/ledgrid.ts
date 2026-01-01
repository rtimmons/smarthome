import { Request as RQ, Response as RS, Router } from 'express';
import * as request from 'request';
import { URL } from 'url';

import { appConfig } from './config';

const app = Router();

const ledgridBase = appConfig.ledgridUrl.replace(/\/+$/, '');
const ledgridHost = new URL(ledgridBase).host;

const ledgridPipe = (path: string, req: RQ, res: RS): void => {
    const url = `${ledgridBase}${path}`;
    const headers = {
        ...req.headers,
        host: ledgridHost,
    } as Record<string, string | string[] | undefined>;
    delete headers['content-length'];

    const options: request.Options = {
        url,
        method: req.method,
        headers,
    };

    const hasJson =
        typeof req.headers['content-type'] === 'string' &&
        req.headers['content-type'].includes('application/json');
    const hasBody =
        req.body &&
        ((typeof req.body === 'object' && Object.keys(req.body).length > 0) ||
            typeof req.body !== 'object');

    if (req.method !== 'GET' && (hasBody || hasJson)) {
        options.body = hasBody ? req.body : {};
        options.json = true;
    }

    const proxy = request(options);

    proxy
        .on('error', (err: any) => {
            console.error(`LEDGrid API error for ${path}:`, err.message);
            if (!res.headersSent) {
                res.status(err.statusCode || 500).json({
                    error: err.message || 'LEDGrid API request failed',
                    route: path,
                });
            }
        })
        .pipe(res);
};

app.post('/ledgrid/start/:animation', (req: RQ, res: RS) => {
    const animation = encodeURIComponent(req.params.animation);
    ledgridPipe(`/api/start/${animation}`, req, res);
});

app.post('/ledgrid/stop', (req: RQ, res: RS) => {
    ledgridPipe('/api/stop', req, res);
});

export const ledgrid = app;
