import * as fs from 'node:fs';
import * as path from 'node:path';
import { createHash } from 'node:crypto';
import { homeModelRoot, loadPlacements, loadRooms } from '../new-hass-configs/config-generator/src/area-placement';
import { callHomeAssistantWs, DEFAULT_HASS_HOST, DEFAULT_HASS_SERVER, fetchState, getAccessToken, runSsh } from '../new-hass-configs/config-generator/src/cli/home-assistant-client';

const digest = (file: string) => createHash('sha256').update(fs.readFileSync(path.join(homeModelRoot, file))).digest('hex');
const xmlText = (text: string) => text.replace(/&(amp|lt|gt|quot|apos|#\d+|#x[0-9a-f]+);/gi, (_, entity: string) =>
  entity.startsWith('#') ? String.fromCodePoint(parseInt(entity.slice(entity[1] === 'x' ? 2 : 1), entity[1] === 'x' ? 16 : 10)) :
    ({ amp: '&', lt: '<', gt: '>', quot: '"', apos: "'" } as Record<string, string>)[entity]);

async function main() {
  const options = { host: DEFAULT_HASS_HOST, server: DEFAULT_HASS_SERVER };
  runSsh(options.host, 'true');
  const token = getAccessToken(options);
  const ws = (kind: string) => callHomeAssistantWs<any[]>(options, token, { type: `config/${kind}_registry/list` });
  const [areas, devices, entities] = await Promise.all(['area', 'device', 'entity'].map(ws));
  const placements = loadPlacements().devices.filter(d => d.platform === 'sonos');
  const rooms = loadRooms();
  const unknown = entities.filter(e => e.platform === 'sonos' && e.entity_id.startsWith('media_player.') && !placements.some(p => p.entityId === e.entity_id));
  if (unknown.length) throw new Error('Review newly discovered Sonos players before recording name agreement');
  const speakers = await Promise.all(placements.map(async placement => {
    const entity = entities.find(e => e.entity_id === placement.entityId);
    const device = devices.find(d => d.id === entity?.device_id);
    if (!device || entity.platform !== 'sonos') throw new Error(`Missing Sonos device: ${placement.entityId}`);
    const state = fetchState(options, token, placement.entityId);
    const areaId = entity.area_id ?? device.area_id ?? null;
    const areaName = areas.find(a => a.area_id === areaId)?.name ?? null;
    // Check speaker names and physical areas against their own catalog fields.
    const expectedName = rooms.rooms.find(r => r.sonosEntityId === placement.entityId)?.name ?? placement.name;
    const expectedAreaName = rooms.areas.find(a => a.id === placement.areaId)?.name ?? null;
    const homeAssistantName = state?.attributes?.friendly_name ?? null;
    const homeAssistantDeviceName = device.name_by_user ?? device.name;
    let sonosName: string | null = null;
    try {
      // Read-only UPnP description, using the address registered by the Sonos
      // integration. Never start the retired node service or query media metadata.
      const url = new URL('/xml/device_description.xml', device.configuration_url);
      if (url.protocol !== 'http:' || url.port !== '1400' || url.username || url.password) throw new Error('Unexpected description URL');
      const response = await fetch(url, { signal: AbortSignal.timeout(6000), redirect: 'error', headers: { Connection: 'close' } });
      if (!response.ok) throw new Error('Speaker description unavailable');
      const name = (await response.text()).match(/<roomName>([^<]*)<\/roomName>/)?.[1];
      if (name) sonosName = xmlText(name);
    } catch { /* A sleeping/offline speaker is unverified, never a successful match. */ }
    const homeAssistantMatches = homeAssistantName === expectedName && homeAssistantDeviceName === expectedName &&
      areaId === placement.areaId && areaName === expectedAreaName;
    return { entityId: placement.entityId, expectedName, sonosName, homeAssistantName, homeAssistantDeviceName,
      areaId, areaName, status: !homeAssistantMatches ? 'mismatch' : sonosName === null ? 'speaker_unreachable' : sonosName === expectedName ? 'matches' : 'mismatch' };
  }));
  const report = { verifiedAt: new Date().toISOString(), catalogSha256: digest('device-catalog.json'), roomsSha256: digest('rooms.json'), speakers };
  console.log(JSON.stringify(report, null, 2));
  if (process.argv.includes('--record-verification')) {
    // Names, areas and outcomes only; no addresses, device IDs, media or credentials.
    fs.writeFileSync(path.join(homeModelRoot, 'speaker-name-verification.json'), JSON.stringify(report, null, 2) + '\n');
  }
  if (speakers.some(s => s.status === 'mismatch')) throw new Error('Speaker name/area mismatch; inspect the comparison');
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
