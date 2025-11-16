import * as bodyParser from 'body-parser';
import * as cors from 'cors';
import * as express from 'express';
import * as morgan from 'morgan';

// The below value matches with stop in package.json.
process.title = 'smhexprsrv';

import {blindControli2c} from "./blindControl-i2c";

const app = express();

// Middleware
app.use(morgan('tiny'));
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));
app.use(cors());

// Blinds API
app.use(blindControli2c);

// Health check endpoint
app.get('/', (req, res) => {
  res.json({ status: 'ok', service: 'blinds-controller' });
});

// Run the server
app.listen(3000, () => console.log('Blinds Controller API listening on port 3000!'));
