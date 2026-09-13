"""Execute the generated deploy shell against a local Docker transport double.

The lease runs the production Python locking code and acquires a real flock;
no NAS, Docker daemon, credentials, network, or media are accessed.
"""
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/dashboard-status-deploy.py'
spec = importlib.util.spec_from_file_location('dashboard_deploy', SCRIPT)
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)

DOCKER = r'''
import fcntl,json,os,signal,subprocess,sys
from pathlib import Path
root=Path(os.environ['FIXTURE_ROOT']); state=root/'state'; args=sys.argv[1:]
if args[:1]==['--config']: args=args[2:]
with (root/'calls.jsonl').open('a') as out: out.write(json.dumps(args)+'\n')
if args[0]=='compose': print('fixture-dashboard')
elif args[0]=='run':
    env=dict(os.environ)
    for index,arg in enumerate(args):
        if arg=='-e' and args[index+1].startswith('UPDATE_READY='):
            env['UPDATE_READY']=args[index+1].split('=',1)[1].replace('/data/state',str(state))
    code=args[args.index('-c')+1].replace('/data/state',str(state))
    with (root/'lease.log').open('w') as log:
        process=subprocess.Popen([sys.executable,'-c',code],env=env,stdout=log,stderr=log)
    (root/'lease.pid').write_text(str(process.pid))
elif args[0]=='rm':
    try: os.kill(int((root/'lease.pid').read_text()),signal.SIGTERM)
    except (FileNotFoundError,ProcessLookupError): pass
elif args[0]=='restart':
    with (state/'locks/cache.lock').open('r+') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: (root/'restart-under-lock').touch()
        else: raise SystemExit('restart without a maintenance lock')
    if os.environ.get('FAIL_RESTART'): raise SystemExit(9)
elif args[0]=='exec': pass
else: raise SystemExit('unexpected Docker command')
'''


class DashboardDeployTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'app with spaces'
        for directory in ('scripts', 'state/locks', 'state/dashboard/runtime/custom-webui', 'compose/qnap', 'package/bin', 'test-bin'):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        (self.root / 'state/locks/cache.lock').write_text('{}')
        self.originals = {}
        for name in ('catalogctl.py', 'catalog-dashboard.py', 'catalog-refresh.js'):
            self.originals[name] = 'prior ' + name
            (self.root / 'scripts' / name).write_text(self.originals[name])
        self.executable(self.root / 'package/bin/docker', DOCKER)
        self.executable(self.root / 'test-bin/sleep', 'import time; time.sleep(0.1)')
        self.env = dict(os.environ, FIXTURE_ROOT=str(self.root), PATH=str(self.root / 'test-bin') + os.pathsep + os.environ['PATH'])

    def executable(self, path, code):
        path.write_text('#!' + sys.executable + '\n' + code)
        path.chmod(0o700)

    def run_deploy(self, assets=False, fail_restart=False):
        shell = deploy.payload(str(self.root / 'compose/qnap'), assets)
        # Substitute only host discovery; keep actual lease/file/restart logic.
        shell = shell.replace('qnap_package=$(/sbin/getcfg container-station Install_Path -f /etc/config/qpkg.conf)',
                              'qnap_package=' + shlex.quote(str(self.root / 'package')))
        return subprocess.run(['/bin/sh'], input=shell, text=True, capture_output=True,
                              env=dict(self.env, **({'FAIL_RESTART': '1'} if fail_restart else {})), timeout=20)

    def assert_lock_released(self):
        with (self.root / 'state/locks/cache.lock').open('r+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.assertEqual(list((self.root / 'state').glob('*.ready')), [])

    def test_busy_cache_leaves_scripts_unchanged_and_never_restarts(self):
        with (self.root / 'state/locks/cache.lock').open('r+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_deploy()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('no scripts changed', result.stderr)
        for name, original in self.originals.items():
            self.assertEqual((self.root / 'scripts' / name).read_text(), original)
        self.assertFalse((self.root / 'restart-under-lock').exists())
        self.assertFalse((self.root / 'state/dashboard-status-backups').exists())
        self.assert_lock_released()

    def test_idle_deploy_backs_up_exact_files_and_preserves_legacy_only_install(self):
        result = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stderr)
        backups = list((self.root / 'state/dashboard-status-backups').iterdir())
        self.assertEqual(len(backups), 1)
        for name, original in self.originals.items():
            self.assertEqual((backups[0] / name).read_text(), original)
            self.assertEqual((self.root / 'scripts' / name).read_bytes(), (deploy.SCRIPTS / name).read_bytes())
        self.assertFalse((self.root / 'scripts/native_library.py').exists())
        self.assertTrue((self.root / 'restart-under-lock').exists())
        self.assert_lock_released()

    def test_existing_native_backend_is_updated_without_new_mounts(self):
        (self.root / 'scripts/native_library.py').write_text('old native')
        result = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / 'scripts/native_library.py').read_bytes(), (deploy.SCRIPTS / 'native_library.py').read_bytes())
        calls = [json.loads(line) for line in (self.root / 'calls.jsonl').read_text().splitlines()]
        self.assertEqual([args for args in calls if args[0]=='compose'], [['compose','ps','-q','dashboard']])

    def test_failed_restart_releases_lease_preserves_backups_and_reports_failure(self):
        result = self.run_deploy(fail_restart=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('Dashboard telemetry deployed', result.stdout)
        self.assertTrue(list((self.root / 'state/dashboard-status-backups').iterdir()))
        self.assert_lock_released()

    def test_assets_update_does_not_take_cache_lock_or_contact_docker(self):
        with (self.root / 'state/locks/cache.lock').open('r+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_deploy(assets=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / 'calls.jsonl').exists())
        self.assertEqual((self.root / 'scripts/catalogctl.py').read_text(), self.originals['catalogctl.py'])
        self.assertEqual((self.root / 'state/dashboard/runtime/custom-webui/custom.js').read_bytes(), (deploy.SCRIPTS / 'catalog-refresh.js').read_bytes())

    def test_both_generated_shell_modes_pass_shellcheck(self):
        for assets in (False, True):
            result = subprocess.run(['shellcheck', '-s', 'sh', '-'], input=deploy.payload('/share/Container/usenet/compose/qnap', assets),
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
