"""Exercise the real Caddy gate against synthetic authorization and app servers."""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cloud_proxy_tests', ROOT/'usenet-infra/tests/test_cloud_ui_proxy.py')
cloud = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cloud)


@unittest.skipUnless(os.environ.get('HOME_PROXY_RUNTIME_TEST') == '1', 'opt-in isolated proxy runtime')
class GatewayTests(unittest.TestCase):
    run_container = classmethod(cloud.ProxyRuntimeTests.run_container.__func__)

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='home-sso-synthetic-', dir=ROOT/'build')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.proxy = 'home-sso-fixture-'+uuid.uuid4().hex[:10]
        cls.upstream = cls.proxy+'-upstream'
        cls.addClassCleanup(lambda: subprocess.run(['podman', 'rm', '-f', cls.upstream, cls.proxy],
                                                   capture_output=True, timeout=30))
        config = (ROOT/'home-proxy/Caddyfile').read_text()
        config = config.replace('admin unix//run/caddy-private/admin.sock', 'admin off')
        config = config.replace('http://:80 {', 'http://:18081 {')
        config = re.sub(r'https://([a-z.]+)', r'http://\1:18443', config)
        config = re.sub(r'^\s*tls .*$', '', config, flags=re.M)
        config = config.replace('192.168.1.163', '127.0.0.1').replace('192.168.1.0/24', '127.0.0.0/8')
        config = config.replace('10.77.0.1', '127.0.0.1')
        path = Path(cls.temporary.name)/'Caddyfile'
        path.write_text(config)
        path.chmod(0o644)
        cls.run_container(['run','--rm','-i','--network','none',cloud.IMAGE,'caddy','adapt',
                           '--config','-','--adapter','caddyfile'],data=config)
        cls.run_container(['run', '-d', '--name', cls.proxy, '--read-only', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '-e', 'SMARTHOME_ARR_AUTH=Basic synthetic-gateway',
            '--mount', f'type=bind,src={path},dst=/etc/caddy/Caddyfile,ro',
            '--tmpfs', '/data:rw,noexec,nosuid,nodev', '--tmpfs', '/config:rw,noexec,nosuid,nodev',
            cloud.IMAGE, 'caddy', 'run', '--config', '/etc/caddy/Caddyfile', '--adapter', 'caddyfile'])
        script = '''
import http.server,json,threading,time
class Handler(http.server.BaseHTTPRequestHandler):
 def do_GET(self):
  if self.server.server_port==9091:
   cookie=self.headers.get('Cookie','')
   status=200 if cookie=='fixture=mfa' else 403 if cookie=='fixture=denied' else 503 if cookie=='fixture=down' else 401
   if self.headers.get('Remote-User') or self.headers.get('X-Forwarded-For')=='spoofed': status=500
   self.send_response(status); self.end_headers(); return
  h=self.headers
  data=json.dumps({'gateway_authenticated':h.get('Authorization')=='Basic synthetic-gateway',
                  'identity_spoofed':bool(h.get('Remote-User') or h.get('X-Auth-Request-User')),
                  'path':self.path}).encode()
  self.send_response(200); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
 def log_message(self,*args): pass
for port in (9091,18080,19696):
 threading.Thread(target=http.server.ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever,daemon=True).start()
while True: time.sleep(60)
'''
        cls.run_container(['run', '-d', '--name', cls.upstream, '--network', 'container:'+cls.proxy,
            '--read-only', '--cap-drop', 'ALL', 'docker.io/library/python:3.14.7-alpine3.24', 'python3', '-c', script])

    def request(self, app, path, cookie=''):
        payload = json.dumps({'app':app,'path':path,'cookie':cookie})
        script = '''
import http.client,json,sys,time
p=json.load(sys.stdin)
for attempt in range(30):
 try:
  c=http.client.HTTPConnection('127.0.0.1',18443,timeout=3)
  c.request('GET',p['path'],headers={'Host':p['app']+'.home.rytim.com','Cookie':p['cookie'],
    'Authorization':'Basic synthetic-attacker','Remote-User':'admin','X-Auth-Request-User':'admin',
    'X-Forwarded-For':'spoofed','X-Forwarded-Host':'attacker.invalid'})
  r=c.getresponse(); body=r.read().decode()
  if r.status==502: time.sleep(.1); continue
  print(json.dumps({'status':r.status,'body':body})); break
 except OSError: time.sleep(.1)
else: raise SystemExit(1)
'''
        try:
            return json.loads(self.run_container(['exec','-i',self.upstream,'python3','-c',script],data=payload))
        except AssertionError as error:
            logs = subprocess.run(['podman','logs',self.proxy],capture_output=True,text=True)
            raise AssertionError((logs.stdout+logs.stderr)[-2500:]) from error

    def test_all_browser_and_api_paths_require_authorization(self):
        for app, base in (('radarr','/radarr'),('sonarr','/sonarr'),('prowlarr',''),('sabnzbd','')):
            for suffix in ('/', '/api/v3/system/status?apikey=synthetic', '/signalr'):
                for cookie, status in (('',401),('fixture=denied',403),('fixture=down',503)):
                    self.assertEqual(self.request(app,base+suffix,cookie)['status'],status)

    def test_authorized_requests_gain_only_the_gateway_credential(self):
        for app, path in (('radarr','/radarr/'),('sonarr','/sonarr/'),('prowlarr','/'),('sabnzbd','/')):
            result=self.request(app,path,'fixture=mfa')
            self.assertEqual(result['status'],200)
            self.assertEqual(json.loads(result['body']),{'gateway_authenticated':True,'identity_spoofed':False,'path':path})

    def test_sibling_paths_remain_unreachable_after_authorization(self):
        for app,path in (('radarr','/sonarr/'),('sonarr','/radarr/'),('prowlarr','/radarr/')):
            self.assertEqual(self.request(app,path,'fixture=mfa')['status'],404)


if __name__=='__main__': unittest.main()
