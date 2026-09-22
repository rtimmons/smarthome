#!/usr/bin/env python3
"""Apply a separately parity-verified repair without allocating a second local file.

Only changed blocks are written. Every original block and the original full-file
hash are durably preserved first. This helper never downloads, imports, deletes,
releases an admission, or alters a canonical library. Its caller must hold the
acquisition lock and establish that the failed scratch file is quiescent.
"""
import hashlib
import json
import os
from pathlib import Path
import stat

BLOCK = 4 * 1024 * 1024
MAX_CHANGED = 64 * 1024 * 1024


class Refused(RuntimeError):
    pass


def stamp(path):
    info = Path(path).lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise Refused('repair requires an unshared regular scratch file')
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def write_record(path, record):
    with Path(path).open('x') as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(record, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    with_dir = os.open(Path(path).parent, os.O_RDONLY)
    try:
        os.fsync(with_dir)
    finally:
        os.close(with_dir)


def prepare(original, verified, receipt_dir, expected_sha256, *, max_changed=MAX_CHANGED):
    original, verified, receipt_dir = map(Path, (original, verified, receipt_dir))
    if len(expected_sha256) != 64 or any(c not in '0123456789abcdef' for c in expected_sha256):
        raise Refused('independent verified SHA-256 required')
    old_stamp, new_stamp = stamp(original), stamp(verified)
    if old_stamp[:2] == new_stamp[:2] or old_stamp[2] != new_stamp[2]:
        raise Refused('repair files must be distinct and equal in size')
    receipt_dir.mkdir(mode=0o700, exist_ok=False)
    old_hash, new_hash = hashlib.sha256(), hashlib.sha256()
    changes, offset, changed_bytes = [], 0, 0
    with original.open('rb') as source, verified.open('rb') as repair:
        while True:
            before, after = source.read(BLOCK), repair.read(BLOCK)
            if len(before) != len(after):
                raise Refused('repair file size changed')
            if not before:
                break
            old_hash.update(before)
            new_hash.update(after)
            if before != after:
                changed_bytes += len(before)
                if changed_bytes > max_changed:
                    raise Refused('changed-block recovery budget exceeded; source untouched')
                item = {'offset': offset, 'size': len(before),
                        'before_sha256': hashlib.sha256(before).hexdigest(),
                        'after_sha256': hashlib.sha256(after).hexdigest()}
                for suffix, data in (('before', before), ('after', after)):
                    with (receipt_dir / f'{offset}.{suffix}').open('xb') as output:
                        os.fchmod(output.fileno(), 0o600)
                        output.write(data)
                        output.flush()
                        os.fsync(output.fileno())
                changes.append(item)
            offset += len(before)
    if stamp(original) != old_stamp or stamp(verified) != new_stamp:
        raise Refused('repair inputs changed; source untouched')
    if new_hash.hexdigest() != expected_sha256:
        raise Refused('independent repair hash differs; source untouched')
    record = {'schema_version': 1, 'original': str(original), 'verified': str(verified),
              'original_stamp': old_stamp, 'bytes': offset,
              'original_sha256': old_hash.hexdigest(), 'repaired_sha256': new_hash.hexdigest(),
              'changed_bytes': changed_bytes, 'blocks': changes}
    write_record(receipt_dir / 'prepared.json', record)
    return record


def apply(receipt_dir):
    receipt_dir = Path(receipt_dir)
    record = json.loads((receipt_dir / 'prepared.json').read_text())
    original = Path(record['original'])
    if list(stamp(original)) != record['original_stamp']:
        raise Refused('scratch file changed since repair preparation')
    # Validate ALL saved before/after blocks before changing any source byte.
    for block in record['blocks']:
        for suffix in ('before', 'after'):
            data = (receipt_dir / f"{block['offset']}.{suffix}").read_bytes()
            if len(data) != block['size'] or hashlib.sha256(data).hexdigest() != block[f'{suffix}_sha256']:
                raise Refused('recovery block differs from durable receipt')
    write_record(receipt_dir / 'applying.json', {'status': 'applying', 'original_sha256': record['original_sha256']})
    descriptor = os.open(original, os.O_RDWR | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'r+b') as stream:
        info = os.fstat(stream.fileno())
        if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns) != tuple(record['original_stamp']):
            raise Refused('scratch file changed before opening')
        for block in record['blocks']:
            stream.seek(block['offset'])
            before = stream.read(block['size'])
            if hashlib.sha256(before).hexdigest() != block['before_sha256']:
                raise Refused('source block changed; preserved original blocks remain available')
            stream.seek(block['offset'])
            stream.write((receipt_dir / f"{block['offset']}.after").read_bytes())
        stream.flush()
        os.fsync(stream.fileno())
        stream.seek(0)
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != record['repaired_sha256']:
        raise Refused('repaired local hash differs; preserve all recovery artifacts')
    write_record(receipt_dir / 'verified.json', {'status': 'verified', 'sha256': actual,
                                               'original_sha256': record['original_sha256']})
    return {'status': 'verified', 'changed_bytes': record['changed_bytes'], 'blocks': len(record['blocks'])}


def restore(receipt_dir):
    """Restore the exact original bytes after an interrupted or completed repair."""
    receipt_dir = Path(receipt_dir)
    record = json.loads((receipt_dir / 'prepared.json').read_text())
    original = Path(record['original'])
    current_stamp = stamp(original)
    if current_stamp[:3] != tuple(record['original_stamp'][:3]):
        raise Refused('original file identity or size changed')
    blocks = {block['offset']: block for block in record['blocks']}
    reconstructed = hashlib.sha256()
    with original.open('rb') as stream:
        offset = 0
        while data := stream.read(BLOCK):
            if offset in blocks:
                block = blocks[offset]
                if hashlib.sha256(data).hexdigest() not in (block['before_sha256'], block['after_sha256']):
                    raise Refused('repaired block was changed by another writer')
                data = (receipt_dir / f'{offset}.before').read_bytes()
                if len(data) != block['size'] or hashlib.sha256(data).hexdigest() != block['before_sha256']:
                    raise Refused('original recovery block is invalid')
            reconstructed.update(data)
            offset += len(data)
    if reconstructed.hexdigest() != record['original_sha256'] or stamp(original) != current_stamp:
        raise Refused('unchanged source bytes differ; refusing rollback')
    descriptor = os.open(original, os.O_RDWR | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'r+b') as stream:
        info = os.fstat(stream.fileno())
        if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns) != current_stamp:
            raise Refused('scratch file changed before rollback')
        for offset in blocks:
            stream.seek(offset)
            stream.write((receipt_dir / f'{offset}.before').read_bytes())
        stream.flush()
        os.fsync(stream.fileno())
        stream.seek(0)
        if hashlib.file_digest(stream, 'sha256').hexdigest() != record['original_sha256']:
            raise Refused('rollback hash differs; preserve recovery artifacts')
    write_record(receipt_dir / 'restored.json', {'status': 'original_bytes_restored',
                                              'sha256': record['original_sha256']})
    return {'status': 'original_bytes_restored'}
