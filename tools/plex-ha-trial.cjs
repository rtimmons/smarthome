#!/usr/bin/env node
'use strict';

// No device service calls, entity writes, media metadata, or persisted credentials.
const fs = require('node:fs');
const path = require('node:path');
const { execFile } = require('node:child_process');
const { promisify } = require('node:util');
const client = require('../new-hass-configs/config-generator/dist/cli/home-assistant-client.js');
const exec = promisify(execFile);
const options = { host: client.DEFAULT_HASS_HOST, server: client.DEFAULT_HASS_SERVER };
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

function summary(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const pct = p => sorted[Math.ceil(p * sorted.length) - 1];
  return { count: sorted.length, median: pct(0.5), p95: pct(0.95), max: sorted.at(-1) };
}

async function hostSample() {
  const command = 'cat /proc/loadavg; head -3 /proc/pressure/cpu; '
    + 'grep -E "MemAvailable:|SwapFree:" /proc/meminfo; '
    + 'ha --raw-json core stats; ha --raw-json apps stats core_zwave_js; '
    + 'ha --raw-json apps stats a0d7b954_plex';
  const { stdout } = await exec('ssh', [...client.getSshOptions(), options.host, command],
    { timeout: 15000, maxBuffer: 65536 });
  return { at: new Date().toISOString(), stats: stdout };
}

async function main() {
  const [phase, destination, durationText = '120'] = process.argv.slice(2);
  const duration = Number(durationText);
  if (!/^[a-z0-9-]+$/.test(phase || '') || !destination || !Number.isInteger(duration)
      || duration < 10 || duration > 900) {
    throw new Error('Usage: plex-ha-trial.cjs <phase> <output.json> [seconds:10..900]');
  }
  fs.mkdirSync(path.dirname(path.resolve(destination)), { recursive: true });
  // Refuse accidental replacement of earlier evidence.
  const fd = fs.openSync(destination, 'wx', 0o600);
  const report = { phase, started: new Date().toISOString(), duration, samples: [], host: [], errors: [] };
  try {
    const token = client.getAccessToken(options);
    const deadline = performance.now() + duration * 1000;
    let nextHost = 0;
    while (performance.now() < deadline) {
      const begin = performance.now();
      const response = await fetch(`${options.server}/api/`, {
        headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(5000),
      });
      await response.text();
      if (!response.ok) throw new Error(`Core API HTTP ${response.status}`);
      const apiMs = performance.now() - begin;
      const scriptStart = performance.now();
      const result = await client.callHomeAssistantWs(options, token, {
        type: 'execute_script',
        sequence: [
          { variables: { started: '{{ as_timestamp(now()) }}' } },
          { delay: { milliseconds: 50 } },
          { variables: { measurement: { elapsed_ms: '{{ (as_timestamp(now()) - started) * 1000 }}' } } },
          { stop: 'Synthetic scheduler probe complete', response_variable: 'measurement' },
        ],
      }, 5000);
      const serverMs = Number(result?.response?.elapsed_ms);
      if (!Number.isFinite(serverMs)) throw new Error('Script did not return a scheduler measurement');
      report.samples.push({ at: new Date().toISOString(), apiMs,
        scriptRoundtripMs: performance.now() - scriptStart, serverMs });
      if (performance.now() >= nextHost) {
        report.host.push(await hostSample());
        nextHost = performance.now() + 10000;
      }
      await sleep(Math.max(0, 1000 - (performance.now() - begin)));
    }
  } catch (error) {
    // Deliberately omit raw API/error payloads from receipts.
    report.errors.push({ kind: error.name, message: 'Probe failed; phase is invalid' });
    process.exitCode = 1;
  } finally {
    report.finished = new Date().toISOString();
    report.summary = Object.fromEntries(['apiMs', 'scriptRoundtripMs', 'serverMs']
      .map(key => [key, summary(report.samples.map(sample => sample[key]))]));
    fs.writeFileSync(fd, JSON.stringify(report, null, 2) + '\n');
    fs.closeSync(fd);
    console.log(JSON.stringify({ phase, summary: report.summary, errors: report.errors }, null, 2));
  }
}

if (require.main === module) main().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
module.exports = { summary };
