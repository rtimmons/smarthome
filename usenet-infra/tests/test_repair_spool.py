import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from contextlib import ExitStack

SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))


def module(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), SCRIPTS / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


setup = module('repair-spool-setup')
admission = module('capacity-admission')


class RepairSpoolTests(unittest.TestCase):
    def test_bound_finish_restores_dependent_arr_before_validation(self):
        events = []
        controller = mock.Mock()
        controller.require_resources.side_effect = lambda: events.append('resources')
        controller.require_dependencies.side_effect = lambda: events.append('dependencies')
        sab = mock.Mock()
        sab.snapshot.return_value = {'paused': False}
        sab.api.return_value = {'status': True}
        value = {'discovery_was_active': True, 'queue': [], 'history': [],
                 'fingerprints': {}, 'source_inventory': {}, 'feeds': [], 'paused': False}
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(Path, 'samefile', return_value=True))
            stack.enter_context(mock.patch.object(setup, 'capacity_module', return_value=mock.Mock(Controller=mock.Mock(return_value=controller))))
            stack.enter_context(mock.patch.object(setup, 'command', side_effect=lambda *args: events.append(args)))
            stack.enter_context(mock.patch.object(setup, 'quiet', return_value={'queue': [], 'history': []}))
            stack.enter_context(mock.patch.object(setup, 'state_fingerprints', return_value={}))
            stack.enter_context(mock.patch.object(setup, 'inventory', return_value={}))
            stack.enter_context(mock.patch.object(setup, 'save_receipt'))
            setup.finish_bound(Path('/fixture'), sab, value, Path('/fixture/receipt'))
        self.assertEqual(events, ['resources', ('systemctl', 'start', 'usenet-discovery.service'), 'dependencies'])
        self.assertEqual(value['phase'], 'verified')

    def test_sab_feed_writes_use_readback_not_status_acknowledgement(self):
        sab = mock.Mock()
        sab.api.side_effect = [{'config': {}}, {'config': {'rss': [{'name': 'fixture', 'enable': 0}]}}]
        setup.set_feed(sab, 'fixture', 0)
        sab.api.side_effect = [{'config': {}}, {'config': {'rss': [{'name': 'fixture', 'enable': 1}]}}]
        with self.assertRaisesRegex(RuntimeError, 'readback_failed'):
            setup.set_feed(sab, 'fixture', 0)

    def test_only_exact_blank_provider_disk_can_be_formatted(self):
        good = {'type': 'disk', 'serial': '12345', 'size': 300 * 1024**3,
                'fstype': None, 'mountpoints': [None]}
        setup.validate_blank_device(good, 12345)
        for key, value in [('type', 'part'), ('serial', '54321'), ('size', 299 * 1024**3),
                           ('fstype', 'ext4'), ('mountpoints', ['/']), ('children', [{}])]:
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'identity_required'):
                setup.validate_blank_device(dict(good, **{key: value}), 12345)

    def test_inventory_refuses_symlinks_and_shared_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source = root / 'synthetic'; source.write_bytes(b'fixture')
            self.assertEqual(setup.inventory(root)['synthetic']['size'], 7)
            (root / 'link').symlink_to(source)
            with self.assertRaisesRegex(RuntimeError, 'symlink_refused'):
                setup.inventory(root)
            (root / 'link').unlink(); os.link(source, root / 'hardlink')
            with self.assertRaisesRegex(RuntimeError, 'shared_or_special'):
                setup.inventory(root)

    def test_receipts_are_private_and_complete(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'receipt.json'
            setup.save(path, {'phase': 'copy_intent'})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(path.read_text()), {'phase': 'copy_intent'})

    def test_setup_receipt_allows_backup_read_without_group_write(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'receipt.json'
            with mock.patch.object(setup.os, 'chown') as chown, mock.patch.object(
                    setup.pwd, 'getpwnam', return_value=mock.Mock(pw_gid=123)):
                setup.save_receipt(path, {'phase': 'prepared'})
            self.assertEqual(path.stat().st_mode & 0o777, 0o640)
            chown.assert_called_once_with(path, 0, 123)
            self.assertEqual(json.loads(path.read_text()), {'phase': 'prepared'})

    def test_separate_volume_capacity_is_used_and_missing_mount_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); config = root / 'config/catalog'; config.mkdir(parents=True)
            (config / 'remote-scratch.json').write_text(json.dumps({'schema_version': 2, 'mode': 'hybrid', 'native_hardlinks': True}))
            marker = config / 'repair-spool.json'
            marker.write_text(json.dumps({'schema_version': 1, 'volume_id': 12345,
                'filesystem_uuid': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'}))
            controller = admission.Controller(root)
            with mock.patch.object(admission.os, 'statvfs', return_value=mock.Mock(f_bavail=123, f_frsize=4096)) as stats:
                self.assertEqual(controller.available(), 123 * 4096)
                stats.assert_called_once_with(root / 'downloads/incomplete')
            with mock.patch.object(admission, 'is_mountpoint', return_value=False):
                with self.assertRaisesRegex(admission.AdmissionError, 'repair_spool_mount_unavailable'):
                    controller.require_repair_spool()
            marker.unlink(); marker.symlink_to(root / 'absent')
            with self.assertRaisesRegex(admission.AdmissionError, 'configuration_invalid'):
                controller.repair_spool()

    def test_volume_marker_cannot_supply_paths_or_override_hybrid_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); config = root / 'config/catalog'; config.mkdir(parents=True)
            (config / 'remote-scratch.json').write_text(json.dumps({'schema_version': 2, 'mode': 'hybrid', 'native_hardlinks': True}))
            marker = config / 'repair-spool.json'
            base = {'schema_version': 1, 'volume_id': 12345, 'filesystem_uuid': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'}
            for values in (dict(base, path='/'), dict(base, volume_id=True), dict(base, filesystem_uuid='../root')):
                marker.write_text(json.dumps(values))
                with self.assertRaisesRegex(admission.AdmissionError, 'configuration_invalid'):
                    admission.Controller(root).repair_spool()

    def test_healthy_volume_cannot_mask_root_disk_pressure(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ('downloads/complete', 'config', 'state/catalog'):
                (root / name).mkdir(parents=True, exist_ok=True)
            controller = admission.Controller(root)
            controller.repair_spool = lambda: root / 'repair'
            controller.require_repair_spool = lambda: None
            controller.remote_scratch = lambda: root / 'downloads/complete/remote'
            controller.available = lambda: 290 * 1024**3
            with mock.patch.object(admission.os, 'statvfs', return_value=mock.Mock(
                    f_files=1_000_000, f_favail=900_000,
                    f_bavail=admission.RESERVE-1, f_frsize=1)):
                with self.assertRaisesRegex(admission.AdmissionError, '^reserve_breached$'):
                    controller.require_resources()


if __name__ == '__main__':
    unittest.main()
