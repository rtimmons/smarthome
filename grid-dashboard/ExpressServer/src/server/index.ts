import * as bodyParser from 'body-parser';
import * as cors from 'cors';
import * as express from 'express';
import * as morgan from 'morgan';
import * as path from 'path';
import * as serveFavicon from 'serve-favicon';

// The below value matches with stop in package.json.
process.title = 'smhexprsrv';

import { appConfig } from './config';
import { hass } from './hass';
import { ledgrid } from './ledgrid';
import { redirs } from './redirs';
import { sonos } from './sonos';

const app = express();
const publicDir = path.join(__dirname, '..', 'public');

// Community middle-ware.
app.use(morgan('tiny'));
app.use(bodyParser.json()); // support json encoded bodies
app.use(bodyParser.urlencoded({ extended: true })); // support encoded bodies
app.use(cors());

// /ui (dashboard ui) middleware
app.use(serveFavicon(path.join(publicDir, 'favicon.ico')));
app.use('/ui', express.static(publicDir));

// Internal API middleware.
app.use(redirs);
app.use(sonos);
app.use(hass);
app.use(ledgrid);

// Serve dashboard at root for ingress (must be last to not override API routes)
app.use('/', express.static(publicDir));

// Run the thing.
app.listen(appConfig.port, () =>
    console.log(`Listening on port ${appConfig.port}!`)
);
