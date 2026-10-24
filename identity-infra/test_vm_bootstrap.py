"""Bootstrap repair must never replace lost keys or rerun after cutover."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import manage
import repair_vm_bootstrap


class BootstrapSafety(unittest.TestCase):
    def test_migrated_guest_cannot_be_repaired_or_started_as_preparation(self):
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary)
            (private/'vm').mkdir()
            (private/'vm/instance.json').write_text(json.dumps({'directory_migrated': True}))
            with patch.object(repair_vm_bootstrap, 'PRIVATE', private):
                with self.assertRaisesRegex(RuntimeError, 'before directory migration'):
                    repair_vm_bootstrap.main()
            with patch.object(manage, 'PRIVATE', private):
                with self.assertRaisesRegex(RuntimeError, 'migrated directory'):
                    manage.payload('vm-start-preparation')

    def test_missing_original_key_is_not_regenerated(self):
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary)
            root = private/'vm'
            (root/'seed').mkdir(parents=True)
            (root/'instance.json').write_text(json.dumps({
                'directory_migrated': False,
                'uuid': '00000000-0000-0000-0000-000000000001'}))
            (root/'seed/user-data').write_text('#cloud-config\n{}\n')
            with patch.object(repair_vm_bootstrap, 'PRIVATE', private), \
                 patch.object(repair_vm_bootstrap, 'keypair') as generate:
                with self.assertRaisesRegex(RuntimeError, 'Restore missing original guest keys'):
                    repair_vm_bootstrap.main()
                generate.assert_not_called()
            self.assertFalse((root/'seed-repair-1').exists())


if __name__ == '__main__':
    unittest.main()
