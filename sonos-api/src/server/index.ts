import express = require('express');
import morgan = require('morgan');

import {appConfig} from './config';
import {installGracefulShutdown} from './graceful-shutdown';
import {createSonosService, type SelectedSonosService} from './sonos-service';

// The value matches the stop script in package.json.
process.title = 'sonos-api-server';

export const createApp = (service: SelectedSonosService): express.Express => {
  const app = express();
  app.use(morgan('tiny'));
  app.use(express.json());
  app.use(express.urlencoded({extended: true}));
  app.get('/health', (_req, res) => {
    const health = service.health();
    res.status(health.statusCode).json(health.body);
  });
  app.use(service.router);
  return app;
};

export const startServer = async (): Promise<void> => {
  const service = createSonosService(appConfig);
  await service.start();
  const app = createApp(service);
  const server = app.listen(appConfig.port, () => {
    console.log(
      `Sonos API listening on port ${appConfig.port} in ${appConfig.backendMode} mode!`
    );
  });
  installGracefulShutdown(server, {
    service: 'sonos-api',
    beforeClose: () => service.stop(),
  });
};

if (require.main === module) {
  void startServer().catch(error => {
    console.error(
      'Sonos API startup failed:',
      error instanceof Error ? error.message : 'unknown startup error'
    );
    process.exitCode = 1;
  });
}
