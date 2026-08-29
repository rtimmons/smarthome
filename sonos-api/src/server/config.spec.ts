import assert from 'node:assert/strict';
import test from 'node:test';

import {loadAppConfig} from './config';

test('an upgraded installation without backend mode remains on node', () => {
  const config = loadAppConfig({SONOS_BASE_URL: 'http://node:5005/'});
  assert.equal(config.backendMode, 'node');
  assert.equal(config.sonosUrl, 'http://node:5005');
});

test('Home Assistant mode uses Supervisor defaults and token', () => {
  const config = loadAppConfig({
    SONOS_BACKEND_MODE: 'home_assistant',
    SUPERVISOR_TOKEN: 'synthetic-token',
  });
  assert.equal(config.backendMode, 'home_assistant');
  assert.equal(config.homeAssistantRestUrl, 'http://supervisor/core/api');
  assert.equal(config.homeAssistantWebSocketUrl, 'ws://supervisor/core/websocket');
  assert.equal(config.homeAssistantToken, 'synthetic-token');
});

test('local development endpoints are injectable without changing add-on options', () => {
  const config = loadAppConfig({
    SONOS_BACKEND_MODE: 'home_assistant',
    HOME_ASSISTANT_REST_URL: 'http://homeassistant.local:8123/api/',
    HOME_ASSISTANT_WEBSOCKET_URL: 'ws://homeassistant.local:8123/api/websocket',
    HOME_ASSISTANT_TOKEN: 'local-token',
  });
  assert.equal(config.homeAssistantRestUrl, 'http://homeassistant.local:8123/api');
  assert.equal(config.homeAssistantWebSocketUrl, 'ws://homeassistant.local:8123/api/websocket');
  assert.equal(config.homeAssistantToken, 'local-token');
});
