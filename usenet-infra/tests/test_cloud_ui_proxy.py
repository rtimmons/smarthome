"""Proxy isolation regressions; opt-in runtime checks use only synthetic data.

Build roles/cloud_ui_proxy/files as localhost/usenet-cloud-ui:caddy-2.11.4-nonroot,
then set CLOUD_UI_PROXY_RUNTIME_TEST=1 to run the actual pinned Caddy checks.
Nothing here connects to the cloud VM, NAS, or real application credentials.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import uuid


ROLE = Path(__file__).resolve().parents[1] / 'ansible/roles/cloud_ui_proxy'
IMAGE = 'localhost/usenet-cloud-ui:caddy-2.11.4-nonroot'


def render(name: str, **values: str) -> str:
    """These templates intentionally use only literal variable substitutions."""
    value = (ROLE / 'templates' / name).read_text()
    for key, replacement in values.items():
        value = value.replace('{{ ' + key + ' }}', replacement)
    if '{{' in value or '{%' in value:
        raise AssertionError('Template contains an unrendered expression')
    return value


class ProxyIsolationTests(unittest.TestCase):
    def test_image_build_context_cannot_include_existing_credentials(self):
        exclusions = (ROLE / 'files/.dockerignore').read_text().splitlines()
        self.assertEqual(exclusions, ['**', '!Dockerfile', '!.dockerignore'])

    def test_only_exact_private_listeners_and_fixed_loopback_upstreams(self):
        config = render('Caddyfile.j2', cloud_vpn_service_ip='10.77.0.1',
                        **{'cloud_ui_auth.username': 'fixture', 'cloud_ui_auth.password_hash': 'fixture'})
        self.assertEqual(config.count('bind 10.77.0.1'), 2)
        self.assertEqual(config.count('import private_auth'), 2)
        self.assertIn('reverse_proxy 127.0.0.1:8080', config)
        self.assertIn('reverse_proxy 127.0.0.1:9696', config)
        self.assertNotIn('0.0.0.0', config)
        self.assertNotIn('[::]', config)

    def test_compose_has_no_host_port_publishing_or_privileged_mounts(self):
        compose = render('compose.yaml.j2', cloud_data_root='/srv/usenet',
                         cloud_vpn_service_ip='10.77.0.1', usenet_uid='1991', usenet_gid='1991')
        for required in ('network_mode: host', 'restart: "no"', 'read_only: true',
                         'cap_drop: [ALL]', 'no-new-privileges:true', 'user: "1991:1991"'):
            self.assertIn(required, compose)
        self.assertNotIn('ports:', compose)
        self.assertNotIn('docker.sock', compose)
        self.assertNotIn('privileged:', compose)

    def test_boot_and_dependency_restart_cannot_bypass_vpn_ordering(self):
        unit = render('usenet-cloud-ui.service.j2', cloud_data_root='/srv/usenet')
        lines = dict(line.split('=', 1) for line in unit.splitlines() if '=' in line)
        dependencies = {'usenet-vpn-address.service', 'usenet-vpn-firewall.service', 'strongswan.service'}
        for directive in ('Requires', 'After', 'PartOf'):
            self.assertTrue(dependencies <= set(lines[directive].split()))
        self.assertIn('--force-recreate', lines['ExecStart'])
        self.assertIn('--pull never', lines['ExecStart'])
        self.assertEqual('/etc/usenet-cloud-ui', lines['WorkingDirectory'])

    def test_credentials_are_validated_before_publication_and_candidates_removed(self):
        tasks = (ROLE / 'tasks/main.yml').read_text()
        self.assertLess(tasks.index('Require safe Argon2id'), tasks.index('Render a private candidate'))
        self.assertLess(tasks.index('Validate the candidate'), tasks.index('Publish only the validated'))
        self.assertIn("cloud_ui_auth_stat.stat.mode == '0600'", tasks)
        self.assertIn('always:', tasks)
        self.assertIn('Remove the temporary credential-bearing configuration', tasks)
        for task in tasks.split('- name:')[1:]:
            if any(token in task for token in ('cloud_ui_auth.', 'cloud_ui_auth:', 'Caddyfile.candidate')):
                self.assertIn('no_log: true', task)


@unittest.skipUnless(os.environ.get('CLOUD_UI_PROXY_RUNTIME_TEST') == '1', 'opt-in isolated Podman runtime test')
class ProxyRuntimeTests(unittest.TestCase):
    @classmethod
    def run_container(cls, args, *, data=None):
        result = subprocess.run(['podman', *args], input=data, text=True,
                                capture_output=True, timeout=45)
        if result.returncode:
            # This opt-in harness only ever holds freshly generated synthetic
            # credentials; bounded runtime diagnostics make local failures useful.
            raise AssertionError('Isolated proxy test failed: ' + result.stderr[:300])
        return result.stdout

    @classmethod
    def setUpClass(cls):
        # The repository is shared with Podman on macOS; the OS private temp
        # directory is not necessarily visible inside its Linux VM.
        build = ROLE.parents[3] / 'build'
        build.mkdir(exist_ok=True)
        cls.directory = tempfile.TemporaryDirectory(prefix='cloud-ui-synthetic-', dir=build)
        cls.addClassCleanup(cls.directory.cleanup)
        cls.proxy = 'cloud-ui-proxy-test-' + uuid.uuid4().hex[:12]
        cls.upstream = cls.proxy + '-upstream'
        cls.addClassCleanup(lambda: subprocess.run(['podman', 'rm', '-f', cls.upstream, cls.proxy],
                                                  capture_output=True, timeout=30))
        cls.restrictions = ['--user', '1991:1991', '--read-only', '--cap-drop', 'ALL',
                            '--security-opt', 'no-new-privileges']
        password_hash = cls.run_container(['run', '--rm', '--network', 'none', *cls.restrictions,
                                           IMAGE, 'caddy', 'hash-password', '--algorithm', 'argon2id',
                                           '--plaintext', 'synthetic-proxy-test']).strip()
        cls.config = render('Caddyfile.j2', cloud_vpn_service_ip='127.0.0.1',
                            **{'cloud_ui_auth.username': 'fixture', 'cloud_ui_auth.password_hash': password_hash})
        cls.adapted = json.loads(cls.run_container(['run', '--rm', '-i', '--network', 'none',
                                                   *cls.restrictions, IMAGE, 'caddy', 'adapt',
                                                   '--config', '-', '--adapter', 'caddyfile'], data=cls.config))
        path = Path(cls.directory.name) / 'Caddyfile'
        path.write_text(cls.config)
        path.chmod(0o644)  # This file contains only a newly generated synthetic test credential.
        cls.run_container(['run', '-d', '--name', cls.proxy, *cls.restrictions,
                           '--mount', f'type=bind,src={path},dst=/etc/caddy/Caddyfile,ro',
                           '--tmpfs', '/data:rw,noexec,nosuid,nodev,mode=1777',
                           '--tmpfs', '/config:rw,noexec,nosuid,nodev,mode=1777', IMAGE,
                           'caddy', 'run', '--config', '/etc/caddy/Caddyfile', '--adapter', 'caddyfile'])
        server = '''
import base64,hashlib,http.server,json,threading,time
class Handler(http.server.BaseHTTPRequestHandler):
 protocol_version='HTTP/1.1'
 def do_GET(self):
  if self.path=='/websocket':
   accept=base64.b64encode(hashlib.sha1((self.headers['Sec-WebSocket-Key']+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
   self.send_response(101); self.send_header('Upgrade','websocket'); self.send_header('Connection','Upgrade')
   self.send_header('Sec-WebSocket-Accept',accept); self.end_headers(); self.wfile.write(bytes([129,5])+b'hello')
   self.wfile.flush(); self.close_connection=True; return
  if self.path.startswith('/redirect'):
   self.send_response(302); self.send_header('Location','http://'+self.headers['Host']+'/login')
   self.send_header('Set-Cookie','fixture=value; Path=/; HttpOnly'); self.send_header('Content-Length','0'); self.end_headers(); return
  body=json.dumps({'path':self.path,'headers':dict(self.headers)}).encode()
  self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(body))); self.end_headers()
  self.wfile.write(body)
 def log_message(self,*args): pass
for port in (8080,9696):
 threading.Thread(target=http.server.ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever,daemon=True).start()
while True: time.sleep(60)
'''
        cls.run_container(['run', '-d', '--name', cls.upstream, '--network', 'container:' + cls.proxy,
                           *cls.restrictions, 'docker.io/library/python:3.14.7-alpine3.24',
                           'python3', '-c', server])

    def request(self, port, *, password=None, path='/', extra=None):
        # Only fixed synthetic credentials and local-container addresses enter this process.
        payload = json.dumps(dict(port=port, password=password, path=path, extra=extra or {}))
        script = '''
import base64,http.client,json,sys,time
p=json.load(sys.stdin)
h=p['extra']
if p['password'] is not None: h['Authorization']='Basic '+base64.b64encode(('fixture:'+p['password']).encode()).decode()
for attempt in range(30):
 try:
  c=http.client.HTTPConnection('127.0.0.1',p['port'],timeout=3); c.request('GET',p['path'],headers=h)
  r=c.getresponse(); body=r.read().decode(); status=r.status
  if status==502: time.sleep(.1); continue
  print(json.dumps({'status':status,'headers':dict(r.getheaders()),'body':body})); break
 except OSError: time.sleep(.1)
else: raise SystemExit(1)
'''
        return json.loads(self.run_container(['exec', '-i', self.upstream, 'python3', '-c', script], data=payload))

    def test_adapted_config_has_no_admin_tls_or_persistent_secret_copy(self):
        self.assertTrue(self.adapted['admin']['disabled'])
        self.assertFalse(self.adapted['admin']['config']['persist'])
        self.assertNotIn('tls', self.adapted['apps'])
        self.assertEqual(self.adapted['logging']['logs']['default']['writer']['output'], 'discard')
        addresses = {address for server in self.adapted['apps']['http']['servers'].values()
                     for address in server['listen']}
        self.assertEqual(addresses, {'127.0.0.1:18080', '127.0.0.1:19696'})

    def test_anonymous_and_wrong_password_fail_for_both_apps_and_nested_paths(self):
        for port in (18080, 19696):
            for password in (None, 'wrong-synthetic-password'):
                for path in ('/', '/api/v1/system/status?apikey=synthetic-test-value', '/signalr'):
                    self.assertEqual(self.request(port, password=password, path=path)['status'], 401)
            self.assertEqual(self.request(port, extra={'Host': 'spoofed.invalid'})['status'], 401)

    def test_valid_auth_reaches_apps_without_credentials_or_spoofed_forwarding_headers(self):
        for port in (18080, 19696):
            response = self.request(port, password='synthetic-proxy-test', path='/test?query=preserved', extra={
                'Host': 'spoofed.invalid',
                'Forwarded': 'for=spoofed', 'X-Forwarded-For': 'spoofed',
                'X-Forwarded-Host': 'spoofed.invalid', 'X-Forwarded-Proto': 'https',
                'X-Real-IP': 'spoofed', 'Remote-User': 'administrator',
                'X-Auth-Request-User': 'administrator', 'Proxy-Authorization': 'synthetic'})
            self.assertEqual(response['status'], 200)
            body = json.loads(response['body'])
            self.assertEqual(body['path'], '/test?query=preserved')
            headers = {key.lower(): value for key, value in body['headers'].items()}
            self.assertEqual(headers['host'], f'127.0.0.1:{port}')
            self.assertFalse(any(key.startswith(('x-forwarded-', 'x-auth-')) for key in headers))
            for name in ('authorization', 'proxy-authorization', 'forwarded', 'x-real-ip', 'remote-user'):
                self.assertNotIn(name, headers)

    def test_redirect_and_cookie_paths_preserve_the_private_origin(self):
        for port in (18080, 19696):
            response = self.request(port, password='synthetic-proxy-test', path='/redirect')
            self.assertEqual(response['status'], 302)
            self.assertEqual(response['headers']['Location'], f'http://127.0.0.1:{port}/login')
            self.assertEqual(response['headers']['Set-Cookie'], 'fixture=value; Path=/; HttpOnly')

    def test_request_urls_and_hashes_never_reach_container_logs(self):
        self.request(18080, password='synthetic-proxy-test', path='/test?apikey=synthetic-log-marker')
        logs = self.run_container(['logs', self.proxy])
        self.assertNotIn('synthetic-log-marker', logs)
        self.assertNotIn('$argon2id$', logs)

    def test_container_readiness_requires_401_at_both_listeners(self):
        check = "wget -S -O /dev/null -T 3 http://127.0.0.1:18080/ 2>&1 | grep -q 'HTTP/1.1 401' && " \
                "wget -S -O /dev/null -T 3 http://127.0.0.1:19696/ 2>&1 | grep -q 'HTTP/1.1 401'"
        self.run_container(['exec', self.proxy, '/bin/sh', '-c', check])

    def test_authenticated_websocket_upgrade_keeps_frames_working(self):
        script = '''
import base64,json,socket
auth=base64.b64encode(b'fixture:synthetic-proxy-test').decode()
with socket.create_connection(('127.0.0.1',19696),timeout=3) as connection:
 request='GET /websocket HTTP/1.1\\r\\nHost: 127.0.0.1:19696\\r\\nAuthorization: Basic '+auth+'\\r\\nUpgrade: websocket\\r\\nConnection: Upgrade\\r\\nSec-WebSocket-Version: 13\\r\\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\\r\\n\\r\\n'
 connection.sendall(request.encode())
 data=b''
 while b'\\r\\n\\r\\n' not in data: data+=connection.recv(4096)
 headers,frame=data.split(b'\\r\\n\\r\\n',1)
 while len(frame)<7:
  part=connection.recv(7-len(frame))
  if not part: break
  frame+=part
 print(json.dumps({'upgraded':b' 101 ' in headers.split(b'\\r\\n')[0],'frame_ok':frame==bytes([129,5])+b'hello'}))
'''
        result = json.loads(self.run_container(['exec', self.upstream, 'python3', '-c', script]))
        self.assertEqual(result, {'upgraded': True, 'frame_ok': True})


if __name__ == '__main__':
    unittest.main()
