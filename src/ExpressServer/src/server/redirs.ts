import {Request as RQ, Response as RS, Router} from "express";
import * as rpn from "request-promise-native";

import {appConfig as cfg} from './config';

// removes port
const host = (req: RQ) => {
    const header = req.headers.host;
    if (header === undefined) {
        return;
    }
    req.headers.host = header.replace(/:\d+$/, '');
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

redirs.get('/b/:to', (req: RQ, res: RS) => {
    const url = urls[req.params['to']](req, res);
    console.log(`/b/${req.params['to']} => ${url}`);
    req.pipe(rpn(url)).pipe(res);
});

redirs.post('/report', (req: RQ, res: RS) => {
    console.log('REPORT', req.body);
    res.send('OK');
});

redirs.get('/journal', (req: RQ, res: RS) => {
    res.redirect(301, `http://${host(req)}:19531/browse`);
});

redirs.get('/', (req: RQ, res: RS) => {
    res.set('Content-Type', 'application/json');
    res.send('{}');
});
