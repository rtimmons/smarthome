import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


deploy = load('sab_buffered_deploy', HERE / 'scripts/sab-buffered.py')
install = load('sab_buffered_install', HERE / 'compose/cloud/sab-buffered/install.py')
verify = load('sab_buffered_verify', HERE / 'compose/cloud/sab-buffered/verify.py')


class BufferedDeploymentTests(unittest.TestCase):
    def test_configuration_diagnostics_never_include_values_or_keys(self):
        changes = deploy.config_differences({'private-key': ['private-before', False]},
                                           {'private-key': ['private-after', 0]})
        self.assertEqual(changes, [
            {'position': [0, 0], 'before_type': 'str', 'after_type': 'str'},
            {'position': [0, 1], 'before_type': 'bool', 'after_type': 'int'},
        ])
        self.assertNotIn('private', json.dumps(changes))

    def test_pause_policy_api_representation_is_normalized_but_changes_are_detected(self):
        def fingerprint(value, reserve='30G'):
            sab = mock.Mock()
            sab.api.return_value = {'config': {'misc': {'pause_on_post_processing': value, 'start_paused': value,
                                                       'download_free': reserve}}}
            return deploy.config_fingerprint(sab)
        self.assertEqual(fingerprint(False), fingerprint(0))
        self.assertEqual(fingerprint(True), fingerprint(1))
        self.assertNotEqual(fingerprint(False), fingerprint(True))
        self.assertNotEqual(fingerprint(False), fingerprint(False, '1G'))
        with self.assertRaisesRegex(RuntimeError, 'sab_pause_policy_type_changed'):
            fingerprint('0')

    def test_owned_pause_restoration_persists_only_the_original_pause_flag(self):
        for preserve in (False, True):
            sab = mock.Mock()
            sab.api.side_effect = [{'status': True}, {'config': {'misc': {'start_paused': 0}}}]
            deploy.restore_maintenance_pause(sab, {'misc': {'preserve_paused_state': preserve, 'start_paused': False}})
            expected = [mock.call('resume')]
            if preserve:
                expected.append(mock.call('set_config', section='misc', keyword='start_paused', value=0))
            self.assertEqual(sab.api.call_args_list, expected)

    def test_unreviewed_upstream_is_refused_before_patching(self):
        with self.assertRaisesRegex(RuntimeError, 'unreviewed_sab_filesystem_source'):
            install.patched(b'import shutil\n')

    def test_integrity_check_rejects_changed_code(self):
        import hashlib
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            files = {}
            for name in ('filesystem.py', 'buffered_copy.py'):
                path = root / 'app/sabnzbd/sabnzbd' / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture\n')
                files['/' + str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest = root / 'opt/sab-buffered/manifest.json'
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({'version': 1, 'files': files}))
            verify.verify(root)
            path.write_text('changed\n')
            with self.assertRaisesRegex(RuntimeError, 'integrity_failed'):
                verify.verify(root)

    def test_any_postprocessing_or_queue_entry_blocks_restart(self):
        for processing, slots, speed in ((1, [], 0), (0, [{'status': 'Paused'}], 0), (0, [], 1)):
            sab = mock.Mock()
            sab.api.side_effect = [{'queue': {'slots': slots, 'kbpersec': speed, 'paused': True, 'status': 'Paused'}},
                                   {'history': {'ppslots': processing}}]
            with self.assertRaisesRegex(RuntimeError, 'sab_busy'):
                deploy.idle(sab, mock.Mock())
            self.assertEqual([c.args[0] for c in sab.api.call_args_list], ['queue', 'history'])

    def test_compose_guard_rejects_unrelated_changes(self):
        before = {'services': {'sabnzbd': {'image': deploy.ORIGINAL_TAG, 'healthcheck': {'old': True}, 'volumes': ['fixed']},
                               'prowlarr': {'image': 'unchanged'}}}
        after = copy.deepcopy(before)
        after['services']['sabnzbd'].update(image=deploy.TAG, healthcheck={'new': True}, pull_policy='never')
        deploy.check_compose_change(copy.deepcopy(before), copy.deepcopy(after))
        after['services']['sabnzbd']['volumes'] = ['different']
        with self.assertRaisesRegex(RuntimeError, 'unrelated_compose'):
            deploy.check_compose_change(before, after)

    def test_only_reviewed_restart_override_is_accepted(self):
        before = {'services': {'sabnzbd': {'image': deploy.ORIGINAL_TAG, 'restart': 'unless-stopped',
                                         'volumes': ['fixed']}, 'prowlarr': {'image': 'unchanged'}}}
        after = copy.deepcopy(before)
        after['services']['sabnzbd']['restart'] = 'no'
        deploy.check_override_change(copy.deepcopy(before), copy.deepcopy(after))
        after['services']['sabnzbd']['volumes'] = ['different']
        with self.assertRaisesRegex(RuntimeError, 'compose_override_requires_review'):
            deploy.check_override_change(copy.deepcopy(before), after)

    def test_library_mapping_rejects_escape_and_other_roots(self):
        for path in ('/etc/passwd', '/library/../../outside', '/storage/TV/synthetic.bin'):
            with self.assertRaises(RuntimeError):
                deploy.library_path(path, 'radarr')

    def test_failed_candidate_restores_old_compose_and_maintenance_pause(self):
        self.check_failed_candidate(False)

    def test_failed_candidate_preserves_manual_pause(self):
        self.check_failed_candidate(True)

    def test_candidate_config_is_checked_after_owned_pause_is_restored(self):
        self.check_failed_candidate(False, configuration_failure=True)

    def check_failed_candidate(self, paused, configuration_failure=False):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            project = root / 'compose/cloud'
            context = project / 'sab-buffered'
            context.mkdir(parents=True)
            state = root / 'state.json'
            candidate = root / 'candidate.json'
            config_file = root / 'config/sabnzbd/sabnzbd.ini'
            config_file.parent.mkdir(parents=True)
            config_file.write_text('unchanged settings fixture')
            (project / 'compose.yaml').write_text('original compose')
            (project / 'compose.buffered.yaml').write_text('candidate compose')
            deploy.save(candidate, {'image_id': 'candidate', 'context': {},
                                   'compose_sha256': deploy.digest(project / 'compose.buffered.yaml')})
            backup = root / 'backups/scheduled/cloud-status.json'
            backup.parent.mkdir(parents=True)
            backup.write_text(json.dumps({'status': 'ok', 'last_success': time.time(),
                                         'archives': [{'remote_ciphertext_verified': True}]}))
            sab = mock.Mock()
            def sab_call(mode, **kwargs):
                if mode == 'queue':
                    return {'queue': {'paused': paused}}
                if mode == 'set_config':
                    return {'config': {'misc': {'start_paused': int(paused)}}}
                return {'status': True}
            sab.api.side_effect = sab_call
            def command(*args, **kwargs):
                if args[:3] == ('docker', 'image', 'save'):
                    Path(args[4]).write_bytes(b'rollback-image-fixture')
                return ''
            fingerprints = []
            def fingerprint(*args, **kwargs):
                kwargs['captured'].update(misc={'preserve_paused_state': True, 'start_paused': paused})
                fingerprints.append(True)
                if len(fingerprints) > 1 and configuration_failure:
                    self.assertEqual([c.args[0] for c in sab.api.call_args_list], ['pause', 'resume', 'set_config'])
                    raise RuntimeError('candidate_failed')
                return 'unchanged'
            with mock.patch.multiple(deploy, ROOT=root, PROJECT=project, CONTEXT=context, STATE=state, CANDIDATE=candidate), \
                 mock.patch.object(deploy, 'live', return_value={'Image': 'base'}), \
                 mock.patch.object(deploy, 'image_info', side_effect=lambda ref: {'Id': 'candidate' if ref == deploy.TAG else 'base'}), \
                 mock.patch.object(deploy, 'module', return_value=mock.Mock(SabSource=lambda: sab, API=mock.Mock())), \
                 mock.patch.object(deploy, 'idle', return_value=paused), \
                 mock.patch.object(deploy, 'active', return_value=False), \
                 mock.patch.object(deploy, 'compose_document'), mock.patch.object(deploy, 'check_compose_change'), \
                 mock.patch.object(deploy, 'reviewed_overrides', return_value=[]), \
                 mock.patch.object(deploy, 'config_fingerprint', side_effect=fingerprint), \
                 mock.patch.object(deploy, 'run', side_effect=command), mock.patch.object(deploy.os, 'chown'), \
                 mock.patch.object(deploy, 'healthy_image', side_effect=[None if configuration_failure else RuntimeError('candidate_failed'), None]):
                with self.assertRaisesRegex(RuntimeError, 'candidate_failed'):
                    deploy.deploy()
            self.assertEqual((project / 'compose.yaml').read_text(), 'original compose')
            self.assertEqual(json.loads(state.read_text())['status'], 'rolled_back')
            self.assertEqual([c.args[0] for c in sab.api.call_args_list],
                             ['queue'] if paused else ['pause', 'resume', 'set_config', 'queue'])

    def test_import_requires_exact_job_file_size_and_native_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            state = root / 'state.json'
            target = root / 'library/TV/synthetic-fixture.bin'
            target.parent.mkdir(parents=True)
            target.write_bytes(b'fixture')
            source = root / 'library/.acquisition-staging/complete/synthetic-job'
            source.mkdir(parents=True)
            value = {'status': 'deployed', 'verification': 'awaiting_next_real_download',
                     'activated_at': 100, 'new_image_id': 'candidate'}
            deploy.save(state, value)
            job = {'nzo_id': 'synthetic-id', 'category': 'sonarr', 'time_added': 200,
                   'status': 'Completed', 'archive': False,
                   'storage': '/data/complete/remote/complete/synthetic-job'}
            record = {'id': 1, 'downloadId': 'different-job', 'eventType': 'downloadFolderImported',
                      'data': {'importedPath': '/library/synthetic-fixture.bin', 'size': '7'}}
            sab, api = mock.Mock(), mock.Mock()
            sab.snapshot.return_value = {'queue': [], 'history': [job]}
            api.call.return_value = {'records': [record], 'totalRecords': 1}
            with mock.patch.multiple(deploy, ROOT=root, STATE=state), \
                 mock.patch.object(deploy, 'healthy_image'), \
                 mock.patch.object(deploy, 'module', return_value=mock.Mock(SabSource=lambda: sab, API=lambda: api)):
                self.assertEqual(deploy.verify_import()['status'], 'awaiting_native_import')
                record['downloadId'] = 'synthetic-id'
                self.assertEqual(deploy.verify_import()['status'], 'awaiting_native_source_cleanup')
                job['archive'] = True
                self.assertEqual(deploy.verify_import()['status'], 'awaiting_native_source_cleanup')
                source.rmdir()
                record['data']['size'] = '8'
                with self.assertRaisesRegex(RuntimeError, 'imported_file_size_mismatch'):
                    deploy.verify_import()
                record['data']['size'] = '7'
                self.assertEqual(deploy.verify_import()['status'], 'verified')
            receipt = json.loads(state.read_text())
            self.assertTrue(receipt['completed_source_removed'])
            self.assertEqual(receipt['imported_files'], 1)


if __name__ == '__main__':
    unittest.main()
