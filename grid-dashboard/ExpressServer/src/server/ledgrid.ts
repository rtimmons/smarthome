import { Request as RQ, Response as RS, Router } from 'express';
import { appConfig } from './config';
import { requestText } from './http';

const app = Router();

const ledgridBase = appConfig.ledgridUrl.replace(/\/+$/, '');

const ledgridPipe = (path: string, req: RQ, res: RS): void => {
    const url = `${ledgridBase}${path}`;
    const hasJson =
        typeof req.headers['content-type'] === 'string' &&
        req.headers['content-type'].includes('application/json');
    const hasBody =
        req.body &&
        ((typeof req.body === 'object' && Object.keys(req.body).length > 0) ||
            typeof req.body !== 'object');

    void requestText(url, {
        method: req.method,
        headers: {
            ...(hasJson ? {'Content-Type': 'application/json'} : {}),
        },
        body:
            req.method !== 'GET' && (hasBody || hasJson)
                ? JSON.stringify(hasBody ? req.body : {})
                : undefined,
    })
        .then(response => {
            res.type(response.headers.get('content-type') || 'application/json')
                .status(response.statusCode)
                .send(response.body);
        })
        .catch((err: unknown) => {
            const message = err instanceof Error ? err.message : 'LEDGrid API request failed';
            console.error(`LEDGrid API error for ${path}:`, message);
            if (!res.headersSent) {
                res.status(502).json({
                    error: message,
                    route: path,
                });
            }
        });
};

app.post('/ledgrid/start/:animation', (req: RQ, res: RS) => {
    const animationParam = req.params.animation;
    const animation = encodeURIComponent(
        Array.isArray(animationParam) ? animationParam[0] || '' : animationParam
    );
    ledgridPipe(`/api/start/${animation}`, req, res);
});

app.post('/ledgrid/stop', (req: RQ, res: RS) => {
    ledgridPipe('/api/stop', req, res);
});

export const ledgrid = app;
