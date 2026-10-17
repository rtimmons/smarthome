import * as fs from 'node:fs';
import * as path from 'node:path';
import {
  callHomeAssistantWs,
  DEFAULT_HASS_HOST,
  DEFAULT_HASS_SERVER,
  getAccessToken,
  runSsh,
} from '../new-hass-configs/config-generator/src/cli/home-assistant-client';

// Deliberately explicit: additional HA areas are never inferred to be obsolete
// just because they have no dashboard tile or Sonos player.
const legacyIds = [
  'bedroom_192', 'hue_room_bathroom', 'hue_room_bedroom',
  'hue_room_kitchen', 'hue_room_living', 'hue_room_office',
];
const root = path.resolve(__dirname, '..');
const model = JSON.parse(fs.readFileSync(path.join(__dirname, 'rooms.json'), 'utf8'));
const options = { host: DEFAULT_HASS_HOST, server: DEFAULT_HASS_SERVER };
const apply = process.argv.includes('--apply');
const cleanup = process.argv.includes('--remove-empty-legacy');

async function main() {
  // SSH must succeed before the existing repository client obtains credentials.
  runSsh(options.host, 'true');
  const token = getAccessToken(options);
  const ws = <T = any>(payload: Record<string, any>) => callHomeAssistantWs<T>(options, token, payload);
  const [areas, devices, entities] = await Promise.all([
    ws<any[]>({ type: 'config/area_registry/list' }),
    ws<any[]>({ type: 'config/device_registry/list' }),
    ws<any[]>({ type: 'config/entity_registry/list' }),
  ]);
  const updates = [];
  for (const desired of model.areas) {
    const area = areas.find(item => item.area_id === desired.id);
    if (!area) throw new Error(`Missing physical area ${desired.id}; manual review required`);
    if (area.name !== desired.name && !desired.aliases.includes(area.name)) {
      throw new Error(`Unexpected name for ${desired.id}; review before renaming`);
    }
    const aliases = [...new Set([...(area.aliases ?? []), ...desired.aliases])];
    if (area.name !== desired.name || aliases.length !== (area.aliases ?? []).length) {
      updates.push({ area_id: desired.id, name: desired.name, aliases });
    }
  }

  // Verify fixed speakers, including Move in Patio. Placement changes use the
  // separate device catalog; area renames never expand the playback allowlist.
  for (const room of model.rooms.filter((item: any) => !item.portable)) {
    const entity = entities.find(item => item.entity_id === room.sonosEntityId);
    const device = devices.find(item => item.id === entity?.device_id);
    if (!entity || (entity.area_id ?? device?.area_id) !== room.areaId) {
      throw new Error(`Unexpected speaker assignment for ${room.name}; review before applying`);
    }
  }

  const candidates = areas.filter(area => legacyIds.includes(area.area_id));
  const occupied = candidates.filter(area =>
    devices.some(device => device.area_id === area.area_id) ||
    entities.some(entity => entity.area_id === area.area_id)
  ).map(area => area.area_id);

  // Scan stored UI configuration, scripts, templates and YAML without returning
  // their content. Both IDs and display names count as references. Disabled
  // entities count above; failure to read/parse the scan fails the operation.
  const quote = (value: string) => "'" + value.replace(/'/g, "'\\''") + "'";
  const references: Record<string, string[]> = {};
  for (const area of candidates) {
    // Fixed-string matching intentionally errs toward retaining an area. `find`
    // propagates read/search errors; grep's ordinary no-match status is accepted.
    const search = 'area_id=$1; area_name=$2; shift 2; ' +
      'grep -F -l -e "$area_id" -e "$area_name" "$@"; result=$?; [ "$result" -le 1 ]';
    const command = 'find /config ' +
      '\\( -type d \\( -name .git -o -name custom_components -o -name deps -o -name www -o -name backups -o -name tts -o -name node_modules \\) -prune \\) -o ' +
      '\\( -type f \\( -path "/config/.storage/*" -o -name "*.yaml" -o -name "*.yml" \\) ' +
      '! -path /config/.storage/core.area_registry ! -path /config/.storage/auth ! -path /config/.storage/auth_provider.homeassistant ' +
      '-exec sh -c ' + quote(search) + ' area-scan ' + quote(area.area_id) + ' ' + quote(area.name) + ' {} + \\)';
    const matches = runSsh(options.host, command);
    references[area.area_id] = matches ? matches.split('\n').map(file => file.replace(/^\/config\//, '')) : [];
  }
  const removable = candidates.filter(area => !occupied.includes(area.area_id) && references[area.area_id].length === 0);
  const summary = {
    mode: apply ? 'apply' : 'audit', updates,
    removable: removable.map(area => area.area_id),
    retained: candidates.filter(area => !removable.includes(area)).map(area => ({
      area_id: area.area_id, occupied: occupied.includes(area.area_id), references: references[area.area_id],
    })),
    fixedSpeakersVerified: model.rooms.filter((room: any) => !room.portable).length,
  };
  console.log(JSON.stringify(summary, null, 2));
  if (!apply) return;

  // Save only area metadata, not media state or credentials, before mutations.
  const evidence = path.join(root, 'build', 'room-alignment', new Date().toISOString().replace(/[:.]/g, '-'));
  fs.mkdirSync(evidence, { recursive: true, mode: 0o700 });
  fs.writeFileSync(path.join(evidence, 'areas-before.json'), JSON.stringify(areas, null, 2), { mode: 0o600 });
  fs.writeFileSync(path.join(evidence, 'plan.json'), JSON.stringify(summary, null, 2), { mode: 0o600 });
  console.log(`Area recovery metadata: ${evidence}`);
  for (const update of updates) {
    await ws({ type: 'config/area_registry/update', ...update });
  }
  if (cleanup) {
    // Recheck membership immediately before deleting each audited empty area.
    for (const area of removable) {
      const [freshDevices, freshEntities] = await Promise.all([
        ws<any[]>({ type: 'config/device_registry/list' }),
        ws<any[]>({ type: 'config/entity_registry/list' }),
      ]);
      if ([...freshDevices, ...freshEntities].some(item => item.area_id === area.area_id)) {
        throw new Error(`Area ${area.area_id} acquired a member; stopping cleanup`);
      }
      await ws({ type: 'config/area_registry/delete', area_id: area.area_id });
    }
  }
  const after = await ws<any[]>({ type: 'config/area_registry/list' });
  fs.writeFileSync(path.join(evidence, 'areas-after.json'), JSON.stringify(after, null, 2), { mode: 0o600 });
  for (const desired of model.areas) {
    const area = after.find(item => item.area_id === desired.id);
    if (area?.name !== desired.name || desired.aliases.some((alias: string) => !area.aliases.includes(alias))) {
      throw new Error(`Area verification failed for ${desired.id}`);
    }
  }
  if (cleanup && removable.some(area => after.some(item => item.area_id === area.area_id))) {
    throw new Error('Legacy area deletion verification failed');
  }
  console.log(`Verified ${after.length} areas; existing area IDs and speaker assignments preserved.`);
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });
