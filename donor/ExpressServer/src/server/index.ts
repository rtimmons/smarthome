import * as bodyParser from 'body-parser';
import * as cors from 'cors';
import * as express from 'express';
import * as morgan from 'morgan';
import * as path from 'path';
import * as serveFavicon from 'serve-favicon';

// The below value matches with stop in package.json.
process.title = 'smhexprsrv';

import {blindControli2c} from "./blindControl-i2c";
import {hass} from './hass';
import {redirs} from './redirs';
import {sonos} from './sonos';

const app = express();

// Community middle-ware.
app.use(morgan('tiny'));
app.use(bodyParser.json()); // support json encoded bodies
app.use(bodyParser.urlencoded({ extended: true })); // support encoded bodies
app.use(cors());

// /ui (dashboard ui) middleware
app.use(serveFavicon(path.join(__dirname, '..', 'public', 'favicon.ico')));
app.use('/ui', express.static('src/public'));

// Internal API middleware.
app.use(redirs);
app.use(sonos);
app.use(hass);
app.use(blindControli2c);

// Run the thing.
app.listen(3000, () => console.log('Listening on port 3000!'));
