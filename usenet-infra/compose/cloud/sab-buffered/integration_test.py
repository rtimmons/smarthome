"""Run with the pinned SAB image's real filesystem module, in isolated /tmp."""
import builtins
import errno
import hashlib
import logging
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, '/app/sabnzbd')
import sabnzbd.filesystem as fs
from sabnzbd.buffered_copy import BufferedCopy, BUFFER_BYTES

assert isinstance(fs.shutil, BufferedCopy), 'SAB must load the installed adapter'
assert fs.shutil.source_root == Path('/data/incomplete')
assert fs.shutil.destination_root == Path('/data/complete/remote/complete')
assert shutil.copyfile.__module__ == 'shutil', 'global shutil must remain untouched'
logging.disable(logging.CRITICAL)
fs.T = lambda value: value


class Integration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sab-copy-test-', dir='/tmp')
        self.root = Path(self.temp.name)
        self.srcroot = self.root / 'source'
        self.dstroot = self.root / 'destination'
        self.srcroot.mkdir()
        self.dstroot.mkdir()
        self.src = self.srcroot / 'synthetic.bin'
        self.dst = self.dstroot / 'synthetic.bin'
        self.payload = os.urandom(BUFFER_BYTES + 37)
        self.src.write_bytes(self.payload)
        self.adapter = BufferedCopy(self.srcroot, self.dstroot)
        self.original_shutil = fs.shutil
        fs.shutil = self.adapter
        self.original_rename = os.rename
        self.rename = patch('os.rename', side_effect=self.cross_device_rename)
        self.rename.start()
        self.overwrite = patch.object(fs.sabnzbd.cfg, 'overwrite_files', return_value=False)
        self.overwrite.start()

    def tearDown(self):
        fs.shutil = self.original_shutil
        self.rename.stop()
        self.overwrite.stop()
        self.temp.cleanup()

    def cross_device_rename(self, source, destination, *args, **kwargs):
        if Path(source).is_relative_to(self.srcroot) and Path(destination).is_relative_to(self.dstroot):
            raise OSError(errno.EXDEV, 'synthetic cross-device move')
        return self.original_rename(source, destination, *args, **kwargs)

    def move(self):
        return fs.move_to_path(str(self.src), str(self.dst), root=str(self.dstroot))

    def assert_preserved_failure(self):
        ok, _ = self.move()
        self.assertFalse(ok)
        self.assertEqual(self.src.read_bytes(), self.payload)
        # Real SAB retries after renamer fails. Both paths must use the adapter.
        self.assertEqual(self.adapter.buffered_copies, 2)

    def test_actual_sab_move_verifies_data_and_metadata_before_source_removal(self):
        self.src.chmod(0o640)
        os.utime(self.src, ns=(1600000000000000000, 1600000000000000000))
        ok, result = self.move()
        self.assertTrue(ok)
        self.assertEqual(result, str(self.dst))
        self.assertFalse(self.src.exists())
        self.assertEqual(self.dst.read_bytes(), self.payload)
        self.assertEqual(self.dst.stat().st_mode & 0o777, 0o640)
        self.assertEqual(self.dst.stat().st_mtime_ns, 1600000000000000000)
        self.assertEqual(self.adapter.buffered_copies, 1)

    def test_fsync_precedes_source_unlink(self):
        real_sync, real_unlink = os.fsync, os.unlink
        events = []
        def sync(fd):
            events.append('sync')
            real_sync(fd)
        def unlink(path, *args, **kwargs):
            if Path(path) == self.src:
                self.assertIn('sync', events)
                events.append('unlink')
            return real_unlink(path, *args, **kwargs)
        with patch('os.fsync', side_effect=sync), patch('os.unlink', side_effect=unlink):
            self.assertTrue(self.move()[0])
        self.assertEqual(events, ['sync', 'unlink'])

    def test_partial_write_failure_preserves_source_across_sab_retry(self):
        def fail(reader, writer, length):
            writer.write(reader.read(4096))
            raise OSError(errno.ENOSPC, 'injected full destination')
        with patch('shutil.copyfileobj', side_effect=fail):
            self.assert_preserved_failure()

    def test_fsync_failure_preserves_source_across_sab_retry(self):
        with patch('os.fsync', side_effect=OSError(errno.EIO, 'injected sync error')):
            self.assert_preserved_failure()

    def test_flush_failure_preserves_source_across_sab_retry(self):
        self.check_stream_failure('flush')

    def test_close_failure_preserves_source_across_sab_retry(self):
        self.check_stream_failure('close')

    def check_stream_failure(self, phase):
        real_open = builtins.open
        class Writer:
            def __init__(self, stream): self.stream = stream
            def __getattr__(self, name): return getattr(self.stream, name)
            def __enter__(self): return self
            def flush(self):
                if phase == 'flush': raise OSError(errno.EIO, 'injected flush error')
                self.stream.flush()
            def __exit__(self, *args):
                self.stream.close()
                if phase == 'close': raise OSError(errno.EIO, 'injected close error')
        def opened(path, mode='r', *args, **kwargs):
            stream = real_open(path, mode, *args, **kwargs)
            return Writer(stream) if Path(path) == self.dst and mode == 'wb' else stream
        with patch('builtins.open', side_effect=opened):
            self.assert_preserved_failure()

    def test_source_change_is_detected(self):
        original = shutil.copyfileobj
        def changed(reader, writer, length):
            original(reader, writer, length)
            with self.src.open('ab') as stream: stream.write(b'changed')
        with patch('shutil.copyfileobj', side_effect=changed):
            self.assertFalse(self.move()[0])
        self.assertTrue(self.src.exists())

    def test_same_filesystem_move_keeps_rename_and_inode(self):
        before = self.src.stat().st_ino
        target = self.srcroot / 'renamed.bin'
        self.adapter.move(str(self.src), str(target))
        self.assertEqual(target.stat().st_ino, before)
        self.assertEqual(self.adapter.buffered_copies, 0)

    def test_existing_destination_uses_sab_unique_name(self):
        self.dst.write_bytes(b'preserve existing')
        ok, result = self.move()
        self.assertTrue(ok)
        self.assertNotEqual(result, str(self.dst))
        self.assertEqual(self.dst.read_bytes(), b'preserve existing')
        self.assertEqual(Path(result).read_bytes(), self.payload)

    def test_destination_escape_refused_by_sab(self):
        self.dstroot.joinpath('escape').symlink_to(self.srcroot, target_is_directory=True)
        self.dst = self.dstroot / 'escape' / 'outside.bin'
        self.assertFalse(self.move()[0])
        self.assertTrue(self.src.exists())
        self.assertEqual(self.adapter.buffered_copies, 0)

    def test_symlink_move_keeps_original_semantics(self):
        self.src.unlink()
        self.src.symlink_to('synthetic-target.bin')
        self.assertTrue(self.move()[0])
        self.assertTrue(self.dst.is_symlink())
        self.assertEqual(os.readlink(self.dst), 'synthetic-target.bin')
        self.assertEqual(self.adapter.buffered_copies, 0)

    def test_same_file_error_never_truncates_source(self):
        os.link(self.src, self.dst)
        with self.assertRaises(shutil.SameFileError):
            self.adapter.copyfile(self.src, self.dst)
        self.assertEqual(self.src.read_bytes(), self.payload)

    def test_outside_roots_uses_standard_copy(self):
        outside = self.root / 'outside.bin'
        self.adapter.copyfile(self.src, outside)
        self.assertEqual(outside.read_bytes(), self.payload)
        self.assertEqual(self.adapter.buffered_copies, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
