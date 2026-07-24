import { Request as RQ, Response as RS, Router } from 'express';

import { appConfig as cfg } from './config';
import { requestText } from './http';

// removes port
const host = (req: RQ) => {
    const header = req.headers.host;
    if (header === undefined) {
        return;
    }
    const sanitized = header.replace(/:\d+$/, '');
    req.headers.host = sanitized;
    return sanitized;
};

export const redirs = Router();

const urls: { [key: string]: (req: RQ, res: RS) => string } = {
    // 1 is up
    '1up': (req: RQ) => `http://${req.headers.host}/up`,
    '1down': (req: RQ) => `http://${req.headers.host}/down`,
    '1left': () => `${cfg.sonosUrl}/Bedroom/favorite/Play%20NPR%20One`,
    '1right': () => `${cfg.sonosUrl}/Bedroom/favorite/Zero%207%20Radio`,
    // 2 is right
    '2right': () => `${cfg.sonosUrl}/Bedroom/next`,
};

redirs.get('/b/:to', async (req: RQ, res: RS) => {
    const targetParam = req.params['to'];
    const target = Array.isArray(targetParam) ? targetParam[0] : targetParam;
    const urlFactory = target ? urls[target] : undefined;
    if (!urlFactory) {
        res.status(404).send('Unknown redirect target');
        return;
    }
    const url = urlFactory(req, res);
    console.log(`/b/${target} => ${url}`);
    try {
        const response = await requestText(url);
        res.type(response.headers.get('content-type') || 'text/plain')
            .status(response.statusCode)
            .send(response.body);
    } catch (err) {
        const message = err instanceof Error ? err.message : 'Redirect target failed';
        res.status(502).json({error: message});
    }
});

redirs.post('/report', (req: RQ, res: RS) => {
    console.log('REPORT', req.body);
    res.send('OK');
});

redirs.get('/journal', (req: RQ, res: RS) => {
    const hostName = host(req) || req.hostname || 'localhost';
    res.redirect(301, `http://${hostName}:19531/browse`);
});

// Root is now handled by static middleware for ingress support
// redirs.get('/', (req: RQ, res: RS) => {
//     res.redirect('/ui/');
// });
