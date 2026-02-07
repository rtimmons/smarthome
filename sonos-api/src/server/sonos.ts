import {Request as RQ, Response as RS, Router} from 'express';
import rpn = require('request-promise-native');

import '../types/sonos';

import {appConfig} from './config';

const app = Router();

const errorStatus = (err: any): number => {
  const statusCode = Number(err && err.statusCode);
  return Number.isFinite(statusCode) && statusCode > 0 ? statusCode : 502;
};

const errorMessage = (err: any, fallback: string): string => {
  if (err && typeof err.message === 'string' && err.message.length > 0) {
    return err.message;
  }
  return fallback;
};

const proxySonosGet = async (route: string, res: RS): Promise<void> => {
  const url = `${appConfig.sonosUrl}/${route}`;

  try {
    const response = await rpn({
      method: 'GET',
      uri: url,
      resolveWithFullResponse: true,
      simple: false,
    });

    res.status(response.statusCode).send(response.body);
  } catch (err) {
    const statusCode = errorStatus(err);
    console.error(`Sonos API upstream error for ${route}:`, err);
    res.status(statusCode).json({
      error: errorMessage(err, 'Sonos upstream request failed'),
      route,
    });
  }
};

const sonosGet = (
  routeFactory: string | ((req: RQ) => string)
): ((req: RQ, res: RS) => Promise<void>) => {
  return async (req: RQ, res: RS) => {
    const route = typeof routeFactory === 'function' ? routeFactory(req) : routeFactory;
    await proxySonosGet(route, res);
  };
};

const wrap = <T>(
  fn: (req: RQ, res: RS) => Promise<T>
): ((req: RQ, res: RS) => Promise<void>) => {
  return async (req: RQ, res: RS) => {
    try {
      await fn(req, res);
    } catch (err) {
      console.error('Sonos API handler error:', err);
      if (!res.headersSent) {
        res.status(errorStatus(err)).json({
          error: errorMessage(err, 'Sonos API request failed'),
        });
      }
    }
  };
};

app.get('/pause', sonosGet('pause'));
app.get('/play', sonosGet('play'));
app.get('/tv', sonosGet('preset/all-tv'));
app.get('/07', sonosGet('favorite/Zero 7 Radio'));
app.get('/quiet', sonosGet('groupVolume/7'));

(() => {
  const rex: RegExp = /sonos\/(.*)$/;
  app.get(rex, wrap(async (req: RQ, res: RS) => {
    const match = req.path.match(rex);
    if (match === null) {
      res.status(400).json({error: `Invalid sonos request ${req.path}`});
      return;
    }
    const rest = match[1];
    await proxySonosGet(rest, res);
  }));
})();

// make all rooms in same zone as :room have volume same as active room
app.get('/same/:room', wrap(async (req: RQ, res: RS) => {
  const room = req.params['room'];
  const zoneResponse = await rpn({
    method: 'GET',
    uri: `${appConfig.sonosUrl}/${room}/zones`,
    resolveWithFullResponse: true,
    simple: false,
  });

  if (zoneResponse.statusCode >= 400) {
    res.status(zoneResponse.statusCode).send(zoneResponse.body);
    return;
  }

  const zones: Sonos.Zone[] = JSON.parse(zoneResponse.body as string);
  // /:room/zones can include all zones; choose the one containing :room.
  const zone = zones.find(z => z.members.some(member => member.roomName === room));
  if (!zone) {
    res.status(404).json({error: `No Sonos zone found containing room ${room}`});
    return;
  }

  const volumes = zone.members.map(m => ({
    roomName: m.roomName,
    volume: m.state.volume,
  }));
  const selfVolume = volumes.find(v => v.roomName === room);
  if (!selfVolume) {
    res.status(404).json({error: `No volume state found for room ${room}`});
    return;
  }

  const others = volumes.filter(v => v.volume !== selfVolume.volume);
  await Promise.all(
    others.map(async other => {
      await rpn({
        method: 'GET',
        uri: `${appConfig.sonosUrl}/${other.roomName}/volume/${selfVolume.volume}`,
        resolveWithFullResponse: true,
        simple: false,
      });
    })
  );

  res.status(200).json({status: 'success'});
}));

app.get('/down', wrap(async (_req: RQ, res: RS) => {
  const stateResponse = await rpn({
    method: 'GET',
    uri: `${appConfig.sonosUrl}/Bedroom/state`,
    resolveWithFullResponse: true,
    simple: false,
  });

  if (stateResponse.statusCode >= 400) {
    res.status(stateResponse.statusCode).send(stateResponse.body);
    return;
  }

  const state = JSON.parse(stateResponse.body as string);
  const path =
    state.playbackState === 'PLAYING' && state.volume <= 3
      ? '/Bedroom/pause'
      : '/Bedroom/groupVolume/-1';

  const updateResponse = await rpn({
    method: 'GET',
    uri: `${appConfig.sonosUrl}${path}`,
    resolveWithFullResponse: true,
    simple: false,
  });

  res.status(updateResponse.statusCode).send(updateResponse.body);
}));

app.get('/up', wrap(async (_req: RQ, res: RS) => {
  const stateResponse = await rpn({
    method: 'GET',
    uri: `${appConfig.sonosUrl}/Bedroom/state`,
    resolveWithFullResponse: true,
    simple: false,
  });

  if (stateResponse.statusCode >= 400) {
    res.status(stateResponse.statusCode).send(stateResponse.body);
    return;
  }

  const state = JSON.parse(stateResponse.body as string);
  const path =
    state.playbackState === 'PAUSED_PLAYBACK'
      ? '/Bedroom/play'
      : '/Bedroom/groupVolume/+1';

  const updateResponse = await rpn({
    method: 'GET',
    uri: `${appConfig.sonosUrl}${path}`,
    resolveWithFullResponse: true,
    simple: false,
  });

  res.status(updateResponse.statusCode).send(updateResponse.body);
}));

export const sonos = app;
