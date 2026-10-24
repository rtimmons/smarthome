"""Exercise encryption failure, restoration, and actual git-clean semantics."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

spec=importlib.util.spec_from_file_location('checkout_state', Path(__file__).with_name('state.py'))
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)

class StateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.age,cls.keygen=s.age_tools()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='checkout-test-',dir='/private/tmp')
        self.base=Path(self.tmp.name)
        self.repo=self.base/'repo';self.repo.mkdir()
        self.state=self.base/'external';self.key=self.base/'key'/'master.agekey'
        subprocess.run(['git','init','-q',str(self.repo)],check=True)
        (self.repo/'.gitignore').write_text('private/\nnode_modules/\nusenet-infra/.env\n')
        subprocess.run(['git','-C',str(self.repo),'add','.gitignore'],check=True)
        (self.repo/'private').mkdir();(self.repo/'private/key').write_bytes(b'fixture-key-bytes\n')
        (self.repo/'private/key').chmod(0o600)
        (self.repo/'usenet-infra').mkdir()
        (self.repo/'usenet-infra/.env').write_text('KEY='+str(self.repo/'private/key')+'\n')
        (self.repo/'node_modules').mkdir();(self.repo/'node_modules/cache').write_text('disposable')
        self.patches=[mock.patch.object(s,'REPO',self.repo),mock.patch.object(s,'check_idle'),mock.patch.object(s,'age_tools',return_value=(self.age,self.keygen))]
        for patch in self.patches:patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):patch.stop()
        self.tmp.cleanup()

    def migrate(self):
        # prepare's repo default is deliberately explicit for the synthetic repo.
        original=s.prepare
        with mock.patch.object(s,'prepare',side_effect=lambda state:original(state,self.repo)):
            s.migrate(self.state,self.key)
        return Path(json.loads((self.state/'recovery/latest.json').read_text())['archive'])

    def test_clean_relinks_preserving_key_and_new_state(self):
        self.migrate()
        self.assertTrue((self.repo/'private').is_symlink())
        (self.repo/'private/new-state').write_text('durable future write')
        subprocess.run(['git','-C',str(self.repo),'clean','-dfx'],check=True,capture_output=True)
        self.assertFalse((self.repo/'private').exists())
        s.prepare(self.state,self.repo)
        self.assertEqual((self.repo/'private/key').read_bytes(),b'fixture-key-bytes\n')
        self.assertEqual((self.repo/'private/new-state').read_text(),'durable future write')
        self.assertFalse((self.repo/'node_modules').exists())

    def test_restore_rebases_config_and_preserves_credential(self):
        archive=self.migrate();destination=self.base/'restore'
        s.restore(archive,self.key,destination,self.age)
        self.assertEqual((destination/'tree/private/key').read_bytes(),b'fixture-key-bytes\n')
        self.assertIn(str(destination/'tree/private/key'),(destination/'tree/usenet-infra/.env').read_text())
        with self.assertRaises(s.StateError):s.restore(archive,self.key,destination,self.age)

    def test_corrupt_ciphertext_leaves_no_destination(self):
        archive=self.migrate();bad=self.base/'bad.age'
        data=bytearray(archive.read_bytes());data[-1]^=1;bad.write_bytes(data)
        destination=self.base/'restore'
        with self.assertRaises(s.StateError):s.restore(bad,self.key,destination,self.age)
        self.assertFalse(destination.exists())

    def test_wrong_key_leaves_no_destination(self):
        archive=self.migrate();other=self.base/'other'/'key'
        s.ensure_key(other,self.keygen)
        destination=self.base/'restore'
        with self.assertRaises(s.StateError):s.restore(archive,other,destination,self.age)
        self.assertFalse(destination.exists())

    def test_terraform_atomic_state_writes_are_external(self):
        import shutil
        tool=self.repo/'tools/checkout/terraform.py';tool.parent.mkdir(parents=True)
        shutil.copyfile(Path(__file__).with_name('terraform.py'),tool)
        config=self.repo/'usenet-infra/terraform/cloud';config.mkdir(parents=True)
        (config/'main.tf').write_text('# synthetic configuration\n')
        subprocess.run(['git','-C',str(self.repo),'add','tools','usenet-infra/terraform/cloud/main.tf'],check=True)
        external=self.state/'tree/usenet-infra/terraform/cloud';external.mkdir(parents=True)
        (self.state/'manifest.json').write_text('{}')
        fake=self.base/'terraform'
        fake.write_text('#!/usr/bin/env python3\nimport pathlib,sys\np=pathlib.Path(sys.argv[1].split("=",1)[1])\n(p/"next").write_text("synthetic state")\n(p/"next").replace(p/"terraform.tfstate")\n')
        fake.chmod(0o700)
        subprocess.run(['python3',str(tool),'-chdir=terraform/cloud','apply'],check=True,
                       env={**os.environ,'SMARTHOME_STATE_DIR':str(self.state),'TERRAFORM_BIN':str(fake)})
        self.assertEqual((external/'terraform.tfstate').read_text(),'synthetic state')
        self.assertFalse((config/'terraform.tfstate').exists())
        self.assertEqual((external/'main.tf').read_text(),'# synthetic configuration\n')

    def test_build_promotion_refuses_unpreserved_data(self):
        self.migrate()
        build=self.repo/'build';build.mkdir()
        (build/'new-record').write_text('must not be silently moved')
        with self.assertRaises(s.StateError):s.promote_build_roots(self.state)
        self.assertFalse(build.is_symlink())
        self.assertTrue((build/'new-record').is_file())

    def test_build_promotion_moves_only_cache_and_preserves_future_writes(self):
        self.migrate()
        cache=self.repo/'build/nvm';cache.mkdir(parents=True)
        (cache/'fixture').write_text('cache')
        (cache/'link').symlink_to('fixture')
        s.promote_build_roots(self.state)
        self.assertTrue((self.repo/'build').is_symlink())
        (self.repo/'build/new-record').write_text('future durable write')
        subprocess.run(['git','-C',str(self.repo),'clean','-dfx'],check=True,capture_output=True)
        s.prepare(self.state,self.repo)
        self.assertEqual((self.repo/'build/new-record').read_text(),'future durable write')

    def test_authenticated_archive_cannot_write_through_symlinks(self):
        import io,tarfile
        self.migrate()
        recipient=subprocess.check_output([str(self.keygen),'-y',str(self.key)]).decode().strip()
        outside=self.base/'untouched';outside.write_text('unchanged')
        for index,files in enumerate((
            {'usenet-infra/.env':{'symlink':str(outside)}},
            {'escape':{'symlink':str(self.base)},'escape/child':{'symlink':'anything'}},
        )):
            envelope={'manifest':s.load_manifest(self.state),'files':files}
            data=json.dumps(envelope).encode();buffer=io.BytesIO()
            with tarfile.open(fileobj=buffer,mode='w:gz') as tar:
                member=tarfile.TarInfo('envelope.json');member.size=len(data)
                tar.addfile(member,io.BytesIO(data))
            archive=self.base/('malicious-'+str(index)+'.age')
            archive.write_bytes(subprocess.check_output([str(self.age),'-r',recipient],input=buffer.getvalue()))
            destination=self.base/('rejected-'+str(index))
            with self.assertRaises(s.StateError):s.restore(archive,self.key,destination,self.age)
            self.assertFalse(destination.exists())
            self.assertEqual(outside.read_text(),'unchanged')

    def test_ui_automations_survive_clean(self):
        config=self.repo/'new-hass-configs';config.mkdir()
        (config/'configuration.yaml').write_text('# synthetic tracked config\n')
        with (self.repo/'.gitignore').open('a') as f:f.write('new-hass-configs/automations.yaml\n')
        subprocess.run(['git','-C',str(self.repo),'add','.gitignore','new-hass-configs/configuration.yaml'],check=True)
        content=b'# Synthetic UI automation state\n[]\n'
        (config/'automations.yaml').write_bytes(content)
        self.assertFalse(s.disposable('new-hass-configs/automations.yaml'))
        self.assertTrue(s.disposable('new-hass-configs/scripts.yaml'))
        self.migrate()
        subprocess.run(['git','-C',str(self.repo),'clean','-dfx'],check=True,capture_output=True)
        s.prepare(self.state,self.repo)
        self.assertEqual((config/'automations.yaml').read_bytes(),content)

    def test_config_upload_copies_contents_and_excludes_external_private_dirs(self):
        source=self.base/'upload';source.mkdir()
        private=self.base/'private-inputs';private.mkdir()
        (private/'automation.yaml').write_text('# synthetic UI state\n[]\n')
        (private/'sensitive.yaml').write_text('synthetic-secret: fixture\n')
        (source/'automations.yaml').symlink_to(private/'automation.yaml')
        (source/'secrets.yaml').symlink_to(private/'sensitive.yaml')
        for name in ('build','backups','inventory_snapshots'):
            (source/name).symlink_to(private,target_is_directory=True)
        destination=self.base/'uploaded';destination.mkdir()
        script=Path(__file__).resolve().parents[2]/'new-hass-configs/sync-tools/deploy-config.sh'
        subprocess.run(['bash','-c','source "$1"; rsync_config -a "$2/" "$3/"',
                        'fixture',str(script),str(source),str(destination)],check=True)
        self.assertFalse((destination/'automations.yaml').is_symlink())
        self.assertEqual((destination/'automations.yaml').read_text(),'# synthetic UI state\n[]\n')
        for name in ('build','backups','inventory_snapshots','secrets.yaml'):
            self.assertFalse((destination/name).exists())
        # Exercise checksum comparison with the platform rsync as well; macOS
        # openrsync fails when asked to checksum the source symlink directly.
        command='source "$1"; CONFIG_DIR="$2"; compare_config "$3/"'
        env={**os.environ,'PATH':'/usr/bin:/bin:'+os.environ['PATH']}
        same=subprocess.check_output(['bash','-c',command,'fixture',str(script),str(source),str(destination)],env=env,text=True)
        self.assertTrue(all(line.startswith('.f..') for line in same.splitlines() if 'automations.yaml' in line))
        timestamp=(private/'automation.yaml').stat()
        (private/'automation.yaml').write_text('# synthetic UI other\n[]\n')
        os.utime(private/'automation.yaml',ns=(timestamp.st_atime_ns,timestamp.st_mtime_ns))
        changed=subprocess.check_output(['bash','-c',command,'fixture',str(script),str(source),str(destination)],env=env,text=True)
        self.assertTrue(any(line[2]=='c' for line in changed.splitlines() if 'automations.yaml' in line))

    def test_conflict_and_traversal_refused(self):
        self.migrate()
        (self.repo/'private').unlink();(self.repo/'private').mkdir()
        with self.assertRaises(s.StateError):s.prepare(self.state,self.repo)
        for name in ('../escape','/absolute','safe/../../escape','.git/config'):
            with self.assertRaises(s.StateError):s.safe_name(name)

if __name__=='__main__':unittest.main()
