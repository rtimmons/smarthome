#!/usr/bin/env python3
import sys,json,urllib.error,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from migrate_jellyfin import Client,PRIVATE,ROOT,PLUGIN,PROVIDER
def main():
 credential=json.loads((ROOT/'usenet-infra/secrets/jellyfin/operator.json').read_text())
 client=Client(credential)
 try:
  before=client.call('/Users')
  receipt=json.loads((PRIVATE/'jellyfin-pre-ad-receipt.json').read_text())
  user=client.call('/Users/Me')
  assert uuid.UUID(user['Id'])==uuid.UUID(receipt['user_id'])
  assert user['Policy']['AuthenticationProviderId']==PROVIDER
  config=client.call('/Plugins/'+PLUGIN+'/Configuration')
  assert config['UseSsl'] and not config['SkipSslVerify'] and not config['CreateUsersFromLdap']
  michael=next(u for u in json.loads((PRIVATE/'human-logins.json').read_text())['users'] if u['username']=='michaellee')
  try:
   unauthorized=Client({'username':'michaellee','password':michael['initial_password']})
  except urllib.error.HTTPError as error:assert error.code in (401,403)
  else:
   unauthorized.logout();raise RuntimeError('Unexpected account access')
  after=client.call('/Users')
  assert {u['Id'] for u in before}=={u['Id'] for u in after}
  assert all(user['Policy'].get(k)==v for k,v in receipt['policy'].items() if k not in ('AuthenticationProviderId','PasswordResetProviderId','InvalidLoginAttemptCount'))
  print('PASS: existing Ryan ID and original permissions; verified LDAPS; Michael denied; no account created')
 finally:client.logout()


if __name__ == '__main__': main()
