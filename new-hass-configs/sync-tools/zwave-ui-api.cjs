// Uses the repository's SSH identity/token flow and Home Assistant ingress.
// Socket.IO polling avoids a second credential store or exposing the app port.
const client = require('../config-generator/dist/cli/home-assistant-client.js');

module.exports = async function callZWaveUI(command) {
  const options = { host: 'root@homeassistant.local', server: 'http://homeassistant.local:8123' };
  const token = client.getAccessToken(options);
  const supervisor = (endpoint, method) => client.callHomeAssistantWs(options, token,
    { type: 'supervisor/api', endpoint, method }, 30000);
  const sessionResponse = await supervisor('/ingress/session', 'post');
  const infoResponse = await supervisor('/addons/core_zwave_js/info', 'get');
  const session = (sessionResponse.data || sessionResponse).session;
  const ingress = (infoResponse.data || infoResponse).ingress_url;
  if (!session || !ingress?.startsWith('/api/hassio_ingress/')) throw Error('Invalid ingress metadata');
  const base = options.server + ingress.replace(/\/$/, '') + '/socket.io/?EIO=4&transport=polling';
  const headers = { Cookie: 'ingress_session=' + session, 'Content-Type': 'text/plain;charset=UTF-8' };
  async function request(url, method = 'GET', body) {
    const response = await fetch(url, { method, headers, body, signal: AbortSignal.timeout(35000) });
    if (!response.ok) throw Error(`Z-Wave ingress HTTP ${response.status}`);
    return response.text();
  }
  const opened = await request(base);
  if (!opened.startsWith('0')) throw Error('Unexpected Socket.IO handshake');
  const url = base + '&sid=' + encodeURIComponent(JSON.parse(opened.slice(1)).sid);
  try {
    await request(url, 'POST', '40');
    // Wait for the Socket.IO namespace acknowledgement before sending the API call.
    await request(url);
    await request(url, 'POST', '421' + JSON.stringify(['ZWAVE_API', command]));
    for (let i = 0; i < 20; i++) {
      for (const packet of (await request(url)).split('\x1e')) {
        if (packet === '2') await request(url, 'POST', '3');
        if (packet.startsWith('431')) {
          const result = JSON.parse(packet.slice(3))[0];
          if (!result.success) throw Error(result.message || 'Z-Wave API call failed');
          return result.result;
        }
      }
    }
    throw Error('No Z-Wave API acknowledgement');
  } finally {
    await request(url, 'POST', '41\x1e1').catch(() => {});
  }
};
