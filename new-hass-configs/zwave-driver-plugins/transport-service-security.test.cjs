const { test } = require('node:test');
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const Plugin = require('./transport-service-security.cjs');

function fixture(version = '15.31.1') {
  const calls = [];
  const driver = {
    controller: { nodes: new Map([[7, {}]]) },
    driverLog: { print() {} },
    isSecurityLevelTooLow(cc) {
      assert.equal(this, driver);
      calls.push(cc);
      return cc.originalResult ?? true;
    },
  };
  const zwave = Object.assign(new EventEmitter(), {
    driver, getInfo: () => ({ zwaveVersion: version }),
  });
  const errors = [];
  const logger = { info() {}, error: message => errors.push(message) };
  const original = driver.isSecurityLevelTooLow;
  const plugin = new Plugin({ zwave, logger });
  return { calls, driver, zwave, errors, original, plugin };
}

function cc(command, name, extra = {}) {
  return { ccId: 0x55, ccCommand: command, nodeId: 7, constructor: { name }, ...extra };
}

test('accepts only the three unencrypted Transport Service control types', async () => {
  const f = fixture();
  for (const [command, name] of [[0xc8, 'TransportServiceCCSegmentRequest'], [0xe8, 'TransportServiceCCSegmentComplete'], [0xf0, 'TransportServiceCCSegmentWait']]) {
    assert.equal(f.driver.isSecurityLevelTooLow(cc(command, name)), false);
  }
  assert.equal(f.calls.length, 0);
  await f.plugin.destroy();
});

test('preserves security checks for payloads, wrong types, and unknown nodes', async () => {
  const f = fixture();
  const unchanged = [
    cc(0xc0, 'TransportServiceCCFirstSegment'),
    cc(0xe0, 'TransportServiceCCSubsequentSegment'),
    cc(0xe8, 'ColorSwitchCCSet', { ccId: 0x33 }),
    cc(0xe8, 'OtherCC'),
    cc(0xe8, 'TransportServiceCCSegmentComplete', { nodeId: 99 }),
    cc(0xe8, 'TransportServiceCCSegmentComplete', { nodeId: [7] }),
    cc(0x03, 'Security2CCMessageEncapsulation', { ccId: 0x9f, originalResult: false }),
    cc(0x03, 'Security2CCMessageEncapsulation', { ccId: 0x9f, originalResult: true }),
  ];
  for (const item of unchanged) {
    assert.equal(f.driver.isSecurityLevelTooLow(item), item.originalResult ?? true);
  }
  assert.deepEqual(f.calls, unchanged);
  await f.plugin.destroy();
});

test('will not patch a different driver version', async () => {
  const f = fixture('15.32.0');
  assert.equal(f.driver.isSecurityLevelTooLow, f.original);
  assert.equal(f.errors.length, 1);
  await f.plugin.destroy();
});

test('ready events are idempotent and shutdown restores the original check', async () => {
  const f = fixture();
  const patched = f.driver.isSecurityLevelTooLow;
  f.zwave.emit('event', 'driver', 'driver ready');
  assert.equal(f.driver.isSecurityLevelTooLow, patched);
  await f.plugin.destroy();
  assert.equal(f.driver.isSecurityLevelTooLow, f.original);
  assert.equal(f.zwave.listenerCount('event'), 0);
});

test('installs if the driver is created after plugin construction', async () => {
  const zwave = Object.assign(new EventEmitter(), { getInfo: () => ({ zwaveVersion: '15.31.1' }) });
  const f = fixture();
  await f.plugin.destroy();
  const plugin = new Plugin({ zwave, logger: { info() {}, error() {} } });
  zwave.driver = f.driver;
  zwave.emit('event', 'driver', 'driver ready');
  assert.notEqual(f.driver.isSecurityLevelTooLow, f.original);
  await plugin.destroy();
});
