'use strict';

// Only the secondary server is writable. Never emit tokens or media metadata.
const fs = require('node:fs');
const BASE = 'http://homeassistant.local:32400';
const LIBRARIES = [
  { name: 'Movies (hass) (Remote)', type: 'movie', agent: 'tv.plex.agents.movie',
    scanner: 'Plex Movie', roots: ['/media/FromDrobo/Remote/files/library/Movies', '/media/FromDrobo/Remote/files/objects/video'] },
  { name: 'TV Shows (hass) (Remote)', type: 'show', agent: 'tv.plex.agents.series',
    scanner: 'Plex TV Series', roots: ['/media/FromDrobo/Remote/files/library/TV'] },
];
const SETTINGS = {
  // PMS 1.43 has separate engine limits. These do NOT enforce one total
  // session: a mixed GPU/CPU test admitted both despite the legacy limit.
  FriendlyName: 'Home Assistant', TranscodeCountLimit: 1,
  '_100215dd100215dd00000500.0-TranscodeCountLimit': 1,
  '_CPU-TranscodeCountLimit': 1,
  HardwareAcceleratedCodecs: 1, HardwareAcceleratedEncoders: 1,
  TranscoderQuality: 0, TranscoderThrottleBuffer: 60,
  autoEmptyTrash: 0, allowMediaDeletion: 0,
  PublishServerOnPlexOnlineKey: 0,
  customConnections: 'http://192.168.1.163:32400,http://homeassistant.local:32400',
  GenerateBIFBehavior: 'never', GenerateIntroMarkerBehavior: 'never',
  GenerateCreditsMarkerBehavior: 'never', GenerateAdMarkerBehavior: 'never',
  GenerateVADBehavior: 'never', GenerateChapterThumbBehavior: 'never',
  LoudnessAnalysisBehavior: 'never', MusicAnalysisBehavior: 'never',
  GenerateIndexFilesDuringAnalysis: 0, ButlerTaskDeepMediaAnalysis: 0,
  ButlerTaskGenerateMediaIndexFiles: 0,
  ScheduledLibraryUpdatesEnabled: 1, ScheduledLibraryUpdateInterval: 3600,
  FSEventLibraryUpdatesEnabled: 0,
};
const LIBRARY_SETTINGS = {
  enableCinemaTrailers: 0, enableBIFGeneration: 0,
  enableCreditsMarkerGeneration: 0, enableAdMarkerGeneration: 0,
  enableVoiceActivityGeneration: 0, enableLoudnessAnalysis: 0,
  enableIntroMarkerGeneration: 0,
};

function connection(token) {
  if (!token || /[\r\n]/.test(token)) throw Error('A valid private Plex token is required');
  return async function request(route, params = {}, method = 'GET') {
    const url = new URL(route, BASE);
    if (url.origin !== BASE) throw Error('Secondary-server origin required');
    for (const [key, value] of Object.entries(params)) {
      for (const item of Array.isArray(value) ? value : [value]) url.searchParams.append(key, String(item));
    }
    const response = await fetch(url, { method, redirect: 'error',
      headers: { 'X-Plex-Token': token, Accept: 'application/json', 'X-Plex-Client-Identifier': 'smarthome-secondary-setup' },
      signal: AbortSignal.timeout(30000) });
    if (!response.ok) throw Error(`Secondary Plex HTTP ${response.status}`);
    const body = await response.text();
    try { return body ? JSON.parse(body) : null; }
    catch { throw Error('Secondary Plex returned an invalid response'); }
  };
}

function verifyLibrary(actual, wanted) {
  const roots = (actual.Location || []).map(x => x.path).sort();
  if (actual.type !== wanted.type || actual.agent !== wanted.agent || actual.scanner !== wanted.scanner
      || JSON.stringify(roots) !== JSON.stringify([...wanted.roots].sort())) {
    throw Error('Existing secondary library differs from the approved roots or agent');
  }
}

async function run(action, token) {
  if (!['configure', 'status', 'libraries'].includes(action)) throw Error('Unknown action');
  const api = connection(token);
  let settings = (await api('/:/prefs')).MediaContainer.Setting;
  if (action === 'configure') {
    const available = new Set(settings.map(s => s.id));
    for (const key of Object.keys(SETTINGS)) if (!available.has(key)) throw Error(`Unsupported setting: ${key}`);
    await api('/:/prefs', SETTINGS, 'PUT');
    settings = (await api('/:/prefs')).MediaContainer.Setting;
    for (const [key, value] of Object.entries(SETTINGS)) {
      const actual = settings.find(s => s.id === key)?.value;
      if (String(typeof actual === 'boolean' ? Number(actual) : actual) !== String(value)) throw Error(`Setting readback failed: ${key}`);
    }
  }
  let sections = (await api('/library/sections')).MediaContainer.Directory || [];
  if (action === 'libraries') {
    // Refuse indexing before the expensive-analysis guards and legacy limit are verified.
    for (const key of ['LoudnessAnalysisBehavior', 'GenerateVADBehavior', 'GenerateCreditsMarkerBehavior', 'TranscodeCountLimit', 'autoEmptyTrash']) {
      const actual = settings.find(s => s.id === key)?.value;
      if (String(typeof actual === 'boolean' ? Number(actual) : actual) !== String(SETTINGS[key])) throw Error('Server guard settings must be configured first');
    }
    for (const wanted of LIBRARIES) {
      let matches = sections.filter(s => s.title === wanted.name);
      if (matches.length > 1) throw Error('Duplicate secondary libraries');
      if (!matches.length) {
        await api('/library/sections', { name: wanted.name, type: wanted.type, agent: wanted.agent,
          scanner: wanted.scanner, language: 'en-US', 'location[]': wanted.roots }, 'POST');
        sections = (await api('/library/sections')).MediaContainer.Directory || [];
        matches = sections.filter(s => s.title === wanted.name);
      }
      if (matches.length !== 1) throw Error('Library creation readback failed');
      verifyLibrary(matches[0], wanted);
      const available = (await api(`/library/sections/${matches[0].key}/prefs`)).MediaContainer.Setting;
      const preferences = Object.fromEntries(Object.entries(LIBRARY_SETTINGS).filter(([key]) => available.some(s => s.id === key)));
      await api(`/library/sections/${matches[0].key}/prefs`, preferences, 'PUT');
      const readback = (await api(`/library/sections/${matches[0].key}/prefs`)).MediaContainer.Setting;
      for (const [key, value] of Object.entries(preferences)) {
        const actual = readback.find(s => s.id === key)?.value;
        if (!['0', 'false'].includes(String(actual)) || value !== 0) throw Error('Library analysis guard readback failed');
      }
    }
  }
  return {
    settings: settings.filter(s => Object.hasOwn(SETTINGS, s.id)).map(({ id, value }) => ({ id, value })),
    libraries: sections.filter(s => LIBRARIES.some(w => w.name === s.title)).map(s => ({ id: s.key, name: s.title, type: s.type, roots: s.Location.map(l => l.path) })),
    activeWork: ((await api('/activities')).MediaContainer.Activity || []).map(({ type, progress }) => ({ type, progress })),
  };
}

module.exports = { run, connection, LIBRARIES, SETTINGS, verifyLibrary };
if (require.main === module) {
  const [action, tokenFile] = process.argv.slice(2);
  if (!tokenFile) throw Error('Usage: plex-secondary.cjs <configure|libraries|status> <private-token-file>');
  run(action, fs.readFileSync(tokenFile, 'utf8').trim()).then(x => console.log(JSON.stringify(x, null, 2)))
    .catch(error => { console.error(error.message); process.exitCode = 1; });
}
