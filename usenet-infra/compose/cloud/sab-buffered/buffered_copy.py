"""SAB-only regular-file copying to synchronous Storage Box staging."""
import os
import hashlib
import logging
import time
from pathlib import Path
import shutil
import stat

BUFFER_BYTES = 1024 * 1024


class BufferedCopy:
    def __init__(self, source_root, destination_root):
        self.source_root = Path(source_root).absolute()
        self.destination_root = Path(destination_root).absolute()
        self.buffered_copies = 0

    def __getattr__(self, name):
        return getattr(shutil, name)

    def eligible(self, source, destination):
        source, destination = Path(source), Path(destination)
        # Never change symlink or special-file behavior. Parent resolution keeps
        # the experimental fast path inside its exact roots, including .. paths.
        if source.is_symlink() or destination.is_symlink():
            return False
        try:
            if not stat.S_ISREG(source.stat().st_mode):
                return False
            if destination.exists() and not stat.S_ISREG(destination.stat().st_mode):
                return False
            return (source.resolve(strict=True).is_relative_to(self.source_root)
                    and destination.parent.resolve(strict=True).is_relative_to(self.destination_root))
        except OSError:
            return False

    def copyfile(self, source, destination, *, follow_symlinks=True):
        if not follow_symlinks or not self.eligible(source, destination):
            return shutil.copyfile(source, destination, follow_symlinks=follow_symlinks)
        if os.path.exists(destination) and os.path.samefile(source, destination):
            raise shutil.SameFileError('source and destination are the same file')
        started = time.monotonic()
        self.buffered_copies += 1
        with open(source, 'rb') as reader:
            before = os.fstat(reader.fileno())
            with open(destination, 'wb') as writer:
                shutil.copyfileobj(reader, writer, length=BUFFER_BYTES)
                writer.flush()
                os.fsync(writer.fileno())
                after = os.fstat(reader.fileno())
                current = os.stat(source)
                if ((before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                        != (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                        or (current.st_dev, current.st_ino) != (after.st_dev, after.st_ino)
                        or writer.tell() != before.st_size):
                    raise OSError('source changed during buffered copy')
        # Close errors propagate before shutil.move or SAB can remove the source.
        logging.info("[storagebox-buffered-v1] copy complete bytes=%d seconds=%.3f source=%s",
                     before.st_size, time.monotonic() - started,
                     hashlib.sha256(os.fsencode(source)).hexdigest())
        return destination

    def copy2(self, source, destination, *, follow_symlinks=True):
        if os.path.isdir(destination):
            destination = os.path.join(destination, os.path.basename(source))
        self.copyfile(source, destination, follow_symlinks=follow_symlinks)
        shutil.copystat(source, destination, follow_symlinks=follow_symlinks)
        return destination

    def move(self, source, destination, copy_function=None):
        # Keep CPython's rename-first behavior, recursive moves, metadata,
        # collisions and symlink semantics. Never mutate the global shutil module.
        return shutil.move(source, destination, copy_function=copy_function or self.copy2)
