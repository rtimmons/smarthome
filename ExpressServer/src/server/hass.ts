import {Request as RQ, Response as RS, Router} from "express";
import * as rpn from "request-promise-native";

const app = Router();

app.get('/scenes/:scene', async (req: RQ, res: RS) => {
    const scene = req.params['scene'];
    const url = 'http://smarterhome.local:8123/api/webhook/' + scene;
    console.log({url});
    await rpn({
        url,
        method: 'post',
    });
    return res.send('OK');
});

export const hass = app;

