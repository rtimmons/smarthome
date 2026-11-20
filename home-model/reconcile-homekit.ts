import * as assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { createHash } from 'node:crypto';
import { homeModelRoot, loadRooms } from '../new-hass-configs/config-generator/src/area-placement';
import { allocatedHomeKitAid, explicitHomeKitFilter, homeKitControls, loadHomeKitCatalog } from '../new-hass-configs/config-generator/src/homekit';
import { callHomeAssistantWs, DEFAULT_HASS_HOST, DEFAULT_HASS_SERVER, getAccessToken, runSsh } from '../new-hass-configs/config-generator/src/cli/home-assistant-client';

const canonical = (value: any): string => JSON.stringify(value, (_key, v) =>
  v && typeof v === 'object' && !Array.isArray(v)
    ? Object.fromEntries(Object.keys(v).sort().map(k => [k, v[k]])) : v);
const digest = (value: any) => createHash('sha256').update(canonical(value)).digest('hex');

async function main() {
  const args = process.argv.slice(2);
  if (args.some(a => !['--apply', '--fixtures-only'].includes(a))) throw new Error('Usage: homekit-audit/homekit-apply [--fixtures-only]');
  const apply = args.includes('--apply');
  const includePresets = !args.includes('--fixtures-only');
  const catalog = loadHomeKitCatalog();
  const controls = homeKitControls(catalog);
  const desired = (includePresets ? controls.includeEntities : controls.fixtures.map(f => f.entityId)).sort();
  const options = { host: DEFAULT_HASS_HOST, server: DEFAULT_HASS_SERVER };
  // Respect the repository's credential-failure boundary before any API access.
  runSsh(options.host, 'true');
  const token = getAccessToken(options);
  const ws = <T = any>(payload: Record<string, any>) => callHomeAssistantWs<T>(options, token, payload);
  const http = async (resource: string, body: any) => {
    const response = await fetch(`${options.server}/api/config/config_entries/options/flow${resource}`, {
      method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body), signal: AbortSignal.timeout(20000),
    });
    if (!response.ok) throw new Error(`HomeKit options flow HTTP ${response.status}`);
    const result = await response.json() as any;
    if (result.errors && Object.keys(result.errors).length) throw new Error(`HomeKit options flow rejected step ${result.step_id}`);
    return result;
  };
  const readBridge = () => {
    const entries = JSON.parse(runSsh(options.host,
      `jq '[.data.entries[] | select(.domain == "homekit")]' /config/.storage/core.config_entries`));
    const matches = entries.filter((e: any) => e.data.name === catalog.bridge.name && e.data.port === catalog.bridge.port);
    if (matches.length !== 1) throw new Error('Expected exactly one existing cataloged HomeKit bridge');
    const entry = matches[0];
    if (entry.source !== 'user' || entry.options.mode !== 'bridge' || !/^[A-Z0-9]{26}$/.test(entry.entry_id)) {
      throw new Error('Unexpected HomeKit bridge identity/source/mode; refusing to recreate or migrate it');
    }
    const prefix = `/config/.storage/homekit.${entry.entry_id}`;
    const state = JSON.parse(runSsh(options.host, `cat ${prefix}.state`));
    const aids = JSON.parse(runSsh(options.host, `cat ${prefix}.aids`));
    const iids = JSON.parse(runSsh(options.host, `cat ${prefix}.iids`));
    if (!Object.keys(state.paired_clients ?? {}).length) throw new Error('Cataloged bridge is not paired; refusing to set up a new pairing');
    const identity = digest({ mac: state.mac, private_key: state.private_key, public_key: state.public_key, paired_clients: state.paired_clients });
    return { entry, state, aids, iids, identity };
  };
  const before = readBridge();
  const [entities, devices, states] = await Promise.all([
    ws<any[]>({ type: 'config/entity_registry/list' }),
    ws<any[]>({ type: 'config/device_registry/list' }),
    ws<any[]>({ type: 'get_states' }),
  ]);
  const areas = new Map(loadRooms().areas.map(a => [a.id, a.name]));
  const names = [];
  for (const id of desired) {
    const entity = entities.find(e => e.entity_id === id);
    const state = states.find(s => s.entity_id === id);
    if (!entity || entity.disabled_by || !state) throw new Error(`Missing or disabled HomeKit control: ${id}`);
    const fixture = controls.fixtures.find(f => f.entityId === id);
    if (!fixture) continue;
    const device = devices.find(d => d.id === entity.device_id);
    if ((entity.area_id ?? device?.area_id) !== fixture.areaId) throw new Error(`Live fixture area drift: ${id}`);
    // Home caches existing names. These HA display names make new exports readable;
    // existing Apple Home names and rooms must also be reconciled in the Home app.
    const name = `${areas.get(fixture.areaId!)} ${fixture.name}`;
    if (entity.name !== name) names.push({ entity_id: id,
      from: { name: entity.name, aliases: entity.aliases ?? [] },
      to: { name, aliases: [...new Set([...(entity.aliases ?? []), state.attributes.friendly_name].filter(Boolean))] },
    });
  }
  const filter = explicitHomeKitFilter(desired);
  const retained = entities.filter(e => desired.includes(e.entity_id))
    .map(e => ({ entityId: e.entity_id, aid: allocatedHomeKitAid(e, before.aids.data.allocations) }))
    .filter(e => e.aid !== undefined);
  assert.ok(retained.length > 0, 'No retained accessory IDs could be resolved; refusing a vacuous preservation check');
  const filterMatches = canonical(before.entry.options.filter) === canonical(filter);
  console.log(JSON.stringify({ mode: apply ? 'apply' : 'audit', bridge: catalog.bridge,
    fixtures: controls.fixtures.length, presets: includePresets ? controls.presets.length : 0,
    exportFilterMatches: filterMatches, haNameUpdates: names.length,
    unavailableFixtures: controls.fixtures.filter(f => states.find(s => s.entity_id === f.entityId)?.state === 'unavailable').map(f => f.entityId),
    homeAppMetadata: 'Room assignments, cached names, switch Display As and native scenes require Apple Home verification',
  }, null, 2));
  if (!apply) return;
  const evidence = path.resolve(homeModelRoot, '../build/homekit-cleanup', new Date().toISOString().replace(/[:.]/g, '-'));
  fs.mkdirSync(evidence, { recursive: true, mode: 0o700 });
  const save = (name: string, value: any) => fs.writeFileSync(path.join(evidence, name), JSON.stringify(value, null, 2) + '\n', { mode: 0o600, flag: 'wx' });
  // Pairing keys and original metadata stay only in ignored, owner-readable evidence.
  save('bridge-before.json', before); save('entity-name-plan.json', names);
  save('export-plan.json', { filter, fixtures: controls.fixtures, presets: includePresets ? controls.presets : [] });
  const fresh = readBridge();
  assert.equal(canonical(fresh.entry), canonical(before.entry), 'Bridge changed since the plan was read');
  assert.equal(fresh.identity, before.identity, 'Pairing changed since the plan was read');
  if (!filterMatches) {
    let flow = await http('', { handler: before.entry.entry_id });
    assert.equal(flow.step_id, 'init');
    flow = await http(`/${flow.flow_id}`, { mode: 'bridge', include_exclude_mode: 'include', domains: [...new Set(desired.map(id => id.split('.')[0]))] });
    assert.equal(flow.step_id, 'include');
    flow = await http(`/${flow.flow_id}`, { entities: desired });
    assert.equal(flow.step_id, 'bridged_device_triggers');
    flow = await http(`/${flow.flow_id}`, { devices: before.entry.options.devices ?? [] });
    assert.equal(flow.type, 'create_entry', 'HomeKit options flow did not finish');
    // HA deliberately omits options data from the completed HTTP response.
    // Verify the persisted entry below instead of assuming response.data exists.
  }
  for (const update of names) await ws({ type: 'config/entity_registry/update', entity_id: update.entity_id, ...update.to });
  let after = readBridge();
  // Storage writes are delayed. Wait for this exact options change, never re-submit it.
  for (let attempt = 0; canonical(after.entry.options.filter) !== canonical(filter) && attempt < 20; attempt++) {
    await new Promise(resolve => setTimeout(resolve, 500)); after = readBridge();
  }
  assert.equal(canonical(after.entry.options.filter), canonical(filter), 'Allowlist readback failed');
  assert.equal(after.entry.entry_id, before.entry.entry_id, 'Bridge entry changed');
  assert.equal(canonical(after.entry.data), canonical(before.entry.data), 'Bridge address/name/port changed');
  assert.equal(after.identity, before.identity, 'HomeKit pairing keys or paired clients changed');
  const afterEntities = await ws<any[]>({ type: 'config/entity_registry/list' });
  for (const retainedEntity of retained) {
    const entity = afterEntities.find(e => e.entity_id === retainedEntity.entityId);
    assert.ok(entity, `Retained entity disappeared: ${retainedEntity.entityId}`);
    assert.equal(allocatedHomeKitAid(entity, after.aids.data.allocations), retainedEntity.aid, `Accessory ID changed: ${retainedEntity.entityId}`);
  }
  for (const update of names) assert.equal(afterEntities.find(e => e.entity_id === update.entity_id)?.name, update.to.name, `HA name readback failed: ${update.entity_id}`);
  save('bridge-after.json', after);
  save('verification.json', { verifiedAt: new Date().toISOString(), fixtures: controls.fixtures.length,
    presets: includePresets ? controls.presets.length : 0, pairingPreserved: true, retainedAccessoryIdsPreserved: retained.length,
    homeAppMetadataVerified: false });
  console.log(`Verified export allowlist and HA display names; existing bridge identity and pairing preserved. Private recovery files: ${evidence}`);
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
