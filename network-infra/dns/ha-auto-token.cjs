// Called only when provisioning the private NAS discovery credential.
const c = require('../../new-hass-configs/config-generator/dist/cli/home-assistant-client.js');
const options = {host: 'root@homeassistant.local', server: 'http://homeassistant.local:8123'};
(async () => {
  const access = c.getAccessToken(options);
  const token = await c.callHomeAssistantWs(options, access, {
    type: 'auth/long_lived_access_token', client_name: 'Household DNS Discovery', lifespan: 3650
  });
  process.stdout.write(JSON.stringify({token}));
})().catch(() => {process.stderr.write('Dedicated DNS token provisioning failed.\n'); process.exit(1);});
