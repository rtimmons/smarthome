#!/usr/bin/env python3
import os,json,secrets,sys,urllib.request,urllib.error,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'identity-infra'))
from manage import PRIVATE
os.umask(0o077)
PLUGIN='958aad66-3784-4d2a-b89a-a7b6fab6e25c'
PROVIDER='Jellyfin.Plugin.LDAP_Auth.LdapAuthenticationProviderPlugin'
class Client:
 def __init__(self,credential):
  self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
  self.headers={'Content-Type':'application/json','Authorization':'MediaBrowser Client="Smarthome identity", Device="Controller", DeviceId="smarthome-ad-migration", Version="1"'}
  self.user=self.call('/Users/AuthenticateByName',{'Username':credential['username'],'Pw':credential['password']})
  self.headers['Authorization']+=', Token="'+self.user['AccessToken']+'"'
 def call(self,path,data=None,method=None):
  with self.opener.open(urllib.request.Request('https://jellyfin.home.rytim.com'+path,headers=self.headers,data=None if data is None else json.dumps(data).encode(),method=method),timeout=45) as r:
   raw=r.read();return json.loads(raw) if raw else None
 def logout(self):
  try:self.call('/Sessions/Logout',{})
  except urllib.error.HTTPError as error:
   if error.code != 401:raise  # Already invalidated sessions need no further action.
def main():
 operator_path=ROOT/'usenet-infra/secrets/jellyfin/operator.json'
 operator=json.loads(operator_path.read_text())
 client=Client(operator)
 try:
  receipt=json.loads((PRIVATE/'jellyfin-pre-ad-receipt.json').read_text())
  user=client.call('/Users/Me');user_id=user['Id']
  assert uuid.UUID(user_id)==uuid.UUID(receipt['user_id']) and user['Name']=='ryan'
  assert not any(s.get('NowPlayingItem') for s in client.call('/Sessions'))
  plugin=next(p for p in client.call('/Plugins') if uuid.UUID(p['Id'])==uuid.UUID(PLUGIN))
  assert plugin['Version']=='24.0.0.0' and plugin['Status']=='Active', 'Plugin must be active'
  config=client.call('/Plugins/'+PLUGIN+'/Configuration')
  original=PRIVATE/'jellyfin-config-before-ad.json'
  if not original.exists():original.write_text(json.dumps(config,indent=2)+'\n')
  ldap=json.loads((PRIVATE/'secrets/jellyfin-ldap.json').read_text())
  assert not config.get('LdapUsers') or all(uuid.UUID(u['LinkedJellyfinUserId'])==uuid.UUID(user_id) for u in config['LdapUsers']), 'Unreviewed LDAP account links; stop'
  config.update(LdapServer='dc1.ad.home.arpa',LdapPort=636,UseSsl=True,UseStartTls=False,SkipSslVerify=False,
   AllowPassChange=False,LdapBindUser='CN=svc-jellyfin,OU=Services,DC=ad,DC=home,DC=arpa',LdapBindPassword=ldap['password'],
   LdapBaseDn='OU=People,DC=ad,DC=home,DC=arpa',LdapRootCaPath='/config/identity/ca.crt',
   LdapClientCertPath='',LdapClientKeyPath='',PasswordResetUrl='',LdapAdminFilter='_disabled_',
   LdapSearchFilter='(&(objectCategory=person)(objectClass=user)(sAMAccountName=ryantimmons)(!(userAccountControl:1.2.840.113556.1.4.803:=2)))',
   LdapSearchAttributes='uid,sAMAccountName',LdapUidAttribute='sAMAccountName',LdapUsernameAttribute='uid',
   CreateUsersFromLdap=False,EnableLdapProfileImageSync=False,EnableAllFolders=False,EnabledFolders=[],
   LdapUsers=[{'LinkedJellyfinUserId':user_id,'LdapUid':'ryantimmons','ProfileImageHash':''}])
  client.call('/Plugins/'+PLUGIN+'/Configuration',config)
  (PRIVATE/'secrets/jellyfin-ldap-configuration.json').write_text(json.dumps(config,indent=2)+'\n')
  result=client.call('/Ldap/TestServerBind',config)
  (PRIVATE/'jellyfin-ldap-bind-result.json').write_text(json.dumps(result)+'\n')
  assert all(result.get(k)=='Success' for k in ('Connect','Bind')) and result.get('BaseSearch','').startswith('Found ') and not result.get('Error'), 'LDAP TLS/bind/search failed; user remains local'
  print('PASS: Jellyfin verified LDAP TLS, dedicated bind and search; no automatic user creation',flush=True)
  recovery_path=PRIVATE/'secrets/jellyfin-recovery.json'
  if not recovery_path.exists():
   with recovery_path.open('x') as stream:stream.write(json.dumps({'username':'smarthome-recovery','password':secrets.token_urlsafe(48)})+'\n')
  recovery=json.loads(recovery_path.read_text())
  users=client.call('/Users')
  matches=[u for u in users if u['Name']==recovery['username']]
  new_account = not matches
  if new_account:
   account=client.call('/Users/New',{'Name':recovery['username']})
   recovery['user_id']=account['Id'];recovery_path.write_text(json.dumps(recovery)+'\n')
  else:
   assert recovery.get('user_id')==matches[0]['Id'],'Unmanaged recovery account; stop'
   account=matches[0]
  rid=account['Id']
  if new_account:
   client.call('/Users/'+rid+'/Password',{'CurrentPw':'','NewPw':recovery['password'],'ResetPassword':False})
  else:
   assert account['Policy']['IsAdministrator'] and not account['Policy']['IsDisabled'], 'Recovery account changed; refusing implicit reset'
  policy=account['Policy'];policy.update(IsAdministrator=True,IsHidden=True,EnableAllFolders=False,EnabledFolders=[])
  assert policy['AuthenticationProviderId']=='Jellyfin.Server.Implementations.Users.DefaultAuthenticationProvider'
  client.call('/Users/'+rid+'/Policy',policy)
  rescue=Client(recovery)
  assert rescue.user['User']['Policy']['IsAdministrator']
  print('PASS: separate local recovery administrator authenticated before changing Ryan',flush=True)
  try:
   old_policy=user['Policy']
   new_policy=dict(old_policy,AuthenticationProviderId=PROVIDER,PasswordResetProviderId=PROVIDER)
   client.call('/Users/'+user_id+'/Policy',new_policy)
   human=next(u for u in json.loads((PRIVATE/'human-logins.json').read_text())['users'] if u['username']=='ryantimmons')
   ad=Client({'username':'ryantimmons','password':human['initial_password']})
   try:
    migrated=ad.call('/Users/Me')
    assert uuid.UUID(migrated['Id'])==uuid.UUID(user_id) and migrated['Name']=='ryan'
    for key,value in old_policy.items():
     if key not in ('AuthenticationProviderId','PasswordResetProviderId','InvalidLoginAttemptCount'):
      assert migrated['Policy'].get(key)==value,'Existing user policy changed: '+key
    seerr=json.loads((ROOT/'usenet-infra/secrets/moonfin/seerr.json').read_text())
    me=ad.call('/Moonfin/Seerr/Api/auth/me')
    assert me['id']==seerr['userId'],'Existing Moonfin account mapping differs'
   finally:ad.logout()
  except BaseException:
   rescue.call('/Users/'+user_id+'/Policy',old_policy)
   raise
  finally:rescue.logout()
  old=PRIVATE/'secrets/jellyfin-operator-before-ad.json'
  if not old.exists():old.write_bytes(operator_path.read_bytes())
  operator['password']=human['initial_password']
  operator_path.write_text(json.dumps(operator,indent=2)+'\n')
  (PRIVATE/'jellyfin-ad-receipt.json').write_text(json.dumps({'user_id':user_id,'provider':PROVIDER,'same_user_id':True,'same_policy_except_provider':True,'moonfin_mapping':'passed','native_ad_password':'passed'})+'\n')
  print('PASS: AD password authenticates existing Ryan ID; permissions and Moonfin linkage preserved',flush=True)
 finally:client.logout()


if __name__ == '__main__': main()
