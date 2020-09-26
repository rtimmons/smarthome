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

app.get('/set_temperature/:entity_id/:temperature', async (req: RQ, res: RS) => {
    const entity_id = req.params['entity_id'];
    const temperature = req.params['temperature'];
    const url = 'http://smarterhome.local:8123/api/service/climate/set_temperature';
    console.log({url});
    await rpn({
        url,
        method: 'post',
        body: {
            entity_id: entity_id,
            temperature: temperature
        },
    });
    return res.send('OK');
});

export const hass = app;

