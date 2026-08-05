import cors = require('cors');
import express = require('express');
import morgan = require('morgan');

// The below value matches with stop in package.json.
process.title = 'sonos-api-server';

import {sonos} from './sonos';
import {appConfig} from './config';
import {installGracefulShutdown} from './graceful-shutdown';

const app = express();

// Community middle-ware.
app.use(morgan('tiny'));
app.use(express.json()); // support json encoded bodies
app.use(express.urlencoded({extended: true})); // support encoded bodies
app.use(cors());

// Sonos API routes
app.use(sonos);

// Health check endpoint
app.get('/health', (req: express.Request, res: express.Response) => {
  res.json({ status: 'ok' });
});

// Run the thing.
const server = app.listen(appConfig.port, () =>
  console.log(`Sonos API listening on port ${appConfig.port}!`),
);
installGracefulShutdown(server, {service: 'sonos-api'});
