import bodyParser = require('body-parser');
import cors = require('cors');
import express = require('express');
import morgan = require('morgan');

// The below value matches with stop in package.json.
process.title = 'sonos-api-server';

import {sonos} from './sonos';
import {appConfig} from './config';

const app = express();

// Community middle-ware.
app.use(morgan('tiny'));
app.use(bodyParser.json()); // support json encoded bodies
app.use(bodyParser.urlencoded({ extended: true })); // support encoded bodies
app.use(cors());

// Sonos API routes
app.use(sonos);

// Health check endpoint
app.get('/health', (req: express.Request, res: express.Response) => {
  res.json({ status: 'ok' });
});

// Run the thing.
app.listen(appConfig.port, () => console.log(`Sonos API listening on port ${appConfig.port}!`));
