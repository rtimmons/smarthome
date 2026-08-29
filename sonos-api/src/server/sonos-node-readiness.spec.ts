import assert from 'node:assert/strict';
import test from 'node:test';

import {createSonosNodeReadinessMonitor} from './sonos-node-readiness';

test('node readiness verifies zones and tracks later upstream failure', async () => {
  let now = 1_000;
  let response: {statusCode: number; body: never[]} | Error = {
    statusCode: 200,
    body: [],
  };
  let scheduled: (() => void) | undefined;
  let cleared = false;
  const monitor = createSonosNodeReadinessMonitor('http://node.test:5005', {
    now: () => now,
    readZones: async url => {
      assert.equal(url, 'http://node.test:5005/zones');
      if (response instanceof Error) throw response;
      return response;
    },
    setInterval: callback => {
      scheduled = callback;
      return 17;
    },
    clearInterval: handle => {
      assert.equal(handle, 17);
      cleared = true;
    },
  });

  assert.deepEqual(monitor.snapshot(), {
    ready: false,
    checkedAt: null,
    error: 'Node Sonos readiness has not been checked',
  });

  await monitor.start();
  assert.deepEqual(monitor.snapshot(), {
    ready: true,
    checkedAt: 1_000,
    statusCode: 200,
  });
  assert.ok(scheduled, 'a periodic readiness refresh is scheduled');

  now = 6_000;
  response = new Error('node unavailable');
  await monitor.check();
  assert.deepEqual(monitor.snapshot(), {
    ready: false,
    checkedAt: 6_000,
    error: 'node unavailable',
  });

  await monitor.stop();
  assert.equal(cleared, true);
});

test('node readiness rejects non-success and malformed zones responses', async () => {
  let response: {statusCode: number; body: unknown} = {
    statusCode: 503,
    body: [],
  };
  const monitor = createSonosNodeReadinessMonitor('http://node.test:5005', {
    now: () => 42,
    readZones: async () => response as {statusCode: number; body: never[]},
    setInterval: () => 1,
    clearInterval: () => undefined,
  });

  await monitor.check();
  assert.deepEqual(monitor.snapshot(), {
    ready: false,
    checkedAt: 42,
    statusCode: 503,
    error: 'Node Sonos zones returned HTTP 503',
  });

  response = {statusCode: 200, body: {not: 'zones'}};
  await monitor.check();
  assert.deepEqual(monitor.snapshot(), {
    ready: false,
    checkedAt: 42,
    statusCode: 200,
    error: 'Node Sonos zones returned an invalid payload',
  });
});
