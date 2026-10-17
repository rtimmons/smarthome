import * as fs from 'node:fs';
import * as path from 'node:path';
import { createHash } from 'node:crypto';
import { homeModelRoot, loadPlacements, loadRooms, planPlacements } from '../new-hass-configs/config-generator/src/area-placement';
import { callHomeAssistantWs, DEFAULT_HASS_HOST, DEFAULT_HASS_SERVER, getAccessToken, runSsh } from '../new-hass-configs/config-generator/src/cli/home-assistant-client';

async function main() {
  const apply = process.argv.includes('--apply');
  const verify = process.argv.includes('--record-verification');
  const options = { host: DEFAULT_HASS_HOST, server: DEFAULT_HASS_SERVER };
  runSsh(options.host, 'true');
  const token = getAccessToken(options);
  const ws = <T = any>(payload: Record<string, any>) => callHomeAssistantWs<T>(options, token, payload);
  const read = async () => {
    const [areas, devices, entities] = await Promise.all([
      ws<any[]>({ type: 'config/area_registry/list' }),
      ws<any[]>({ type: 'config/device_registry/list' }),
      ws<any[]>({ type: 'config/entity_registry/list' }),
    ]);
    return { areas, devices, entities };
  };
  const catalog = loadPlacements();
  const rooms = loadRooms();
  const before = await read();
  const plan = (state: typeof before) => {
    for (const area of rooms.areas) {
      if (!state.areas.some(a => a.area_id === area.id && a.name === area.name)) throw new Error(`Area name/ID drift: ${area.id}`);
    }
    return planPlacements(catalog, state.areas.map(a => a.area_id), state.devices, state.entities);
  };
  const proposed = plan(before);
  console.log(JSON.stringify({ ...proposed, updates: proposed.updates.map(({ id, ...safe }) => safe) }, null, 2));
  if (proposed.uncovered.length) throw new Error('Review uncataloged entities before applying or recording verification');
  let after = before;
  if (apply && proposed.updates.length) {
    const evidence = path.join(homeModelRoot, '../build/room-alignment', new Date().toISOString().replace(/[:.]/g, '-'));
    fs.mkdirSync(evidence, { recursive: true, mode: 0o700 });
    const save = (name: string, value: unknown) => fs.writeFileSync(path.join(evidence, name), JSON.stringify(value, null, 2), { mode: 0o600 });
    save('placements-before.json', before); save('placement-plan.json', proposed);
    console.log(`Private recovery metadata: ${evidence}`);
    // Re-read just before the batch, rejecting concurrent area or device changes.
    if (JSON.stringify(plan(await read())) !== JSON.stringify(proposed)) throw new Error('Placement plan changed; rerun audit');
    for (const update of proposed.updates) {
      await ws({ type: `config/${update.scope}_registry/update`,
        [update.scope === 'device' ? 'device_id' : 'entity_id']: update.id, area_id: update.to });
    }
    after = await read(); save('placements-after.json', after);
    if (plan(after).updates.length) throw new Error('Area assignment verification failed; inspect saved evidence');
  }
  if (verify) {
    const final = plan(after);
    if (final.updates.length || final.uncovered.length || final.retiredPresent.length) throw new Error('Catalog is not fully reconciled');
    const effective = (e: any) => e.area_id ?? after.devices.find(d => d.id === e.device_id)?.area_id ?? null;
    // Deliberately curated totals only: no registry dumps, device IDs, state,
    // credentials, network addresses or incidental media metadata enter the wiki.
    const report = {
      verifiedAt: new Date().toISOString(),
      catalogSha256: createHash('sha256').update(fs.readFileSync(path.join(homeModelRoot, 'device-catalog.json'))).digest('hex'),
      coveredDevices: final.coveredDevices, coveredEntities: final.coveredEntities,
      devicesWithoutEntities: final.devicesWithoutEntities,
      absent: final.absent,
      areas: [...rooms.areas.map(a => ({ areaId: a.id })), { areaId: null }].map(a => ({ ...a,
        devices: after.devices.filter(d => (d.area_id ?? null) === a.areaId).length,
        entities: after.entities.filter(e => effective(e) === a.areaId).length,
        disabledEntities: after.entities.filter(e => effective(e) === a.areaId && e.disabled_by != null).length,
      })),
    };
    fs.writeFileSync(path.join(homeModelRoot, 'area-verification.json'), JSON.stringify(report, null, 2) + '\n');
    console.log('Saved dated, sanitized area verification totals. This is not availability or hardware testing.');
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
