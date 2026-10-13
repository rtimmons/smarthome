const c=require('../../new-hass-configs/config-generator/dist/cli/home-assistant-client.js');
const options={host:'root@homeassistant.local',server:'http://homeassistant.local:8123'};
const token=c.getAccessToken(options);
(async()=>{
 const session=await c.callHomeAssistantWs(options,token,{type:'supervisor/api',endpoint:'/ingress/session',method:'post'});
 const info=await c.callHomeAssistantWs(options,token,{type:'supervisor/api',endpoint:'/addons/a0d7b954_adguard/info',method:'get'});
 process.stdout.write(JSON.stringify({session:session.session,prefix:info.ingress_url}));
})().catch(()=>{process.stderr.write('Unable to create an authenticated AdGuard ingress session.\n');process.exit(1)});
