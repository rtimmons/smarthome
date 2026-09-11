#!/usr/bin/env python3
"""Validate recovery inventory and local file metadata; never read secret bytes.

This is an inventory gate, not a decryption or deletion-safety check. Only the
public manifest and Git's path metadata are read. Private files are never opened.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'usenet-infra/recovery/inventory.json'
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


class InventoryError(Exception):
    pass


def exact_path(value):
    if (not isinstance(value, str) or not value or
            re.search(r'[\x00-\x1f\x7f\\*?\[\]]', value) or
            value.startswith('/') or value != str(PurePosixPath(value)) or
            any(part in ('.', '..') for part in value.split('/'))):
        raise InventoryError('invalid repository-relative path')
    return value


def text_field(value):
    if not isinstance(value, str) or not value.strip():
        raise InventoryError('missing descriptive metadata')


def text_list(value):
    if not isinstance(value, list) or not value:
        raise InventoryError('missing metadata list')
    for item in value:
        text_field(item)


def validate_manifest(data):
    if (not isinstance(data, dict) or set(data) != {
            'schema_version', 'scope', 'files', 'scan_roots', 'exclusions',
            'external_dependencies', 'deletion_safe'} or
            type(data['schema_version']) is not int or data['schema_version'] != 1 or
            data['scope'] != 'smarthome' or data['deletion_safe'] is not False):
        raise InventoryError('unsupported inventory schema or readiness claim')
    if not isinstance(data['files'], list) or not data['files']:
        raise InventoryError('empty file inventory')
    ids, paths = set(), set()
    fields = {'id', 'path', 'restore_path', 'owner', 'sensitivity', 'mode',
              'format', 'consumers', 'backup_dependency', 'rotation', 'category',
              'required', 'path_policy', 'evidence'}
    for entry in data['files']:
        if not isinstance(entry, dict) or set(entry) != fields:
            raise InventoryError('invalid file entry fields')
        path = exact_path(entry['path'])
        if exact_path(entry['restore_path']) != path:
            raise InventoryError('restore destination must equal inventoried path')
        if (not isinstance(entry['id'], str) or
                not re.fullmatch(r'[a-z][a-z0-9-]*', entry['id']) or
                entry['id'] in ids or path in paths):
            raise InventoryError('invalid or duplicate inventory identity/path')
        ids.add(entry['id'])
        paths.add(path)
        for field in ('owner', 'format', 'rotation'):
            text_field(entry[field])
        for field in ('consumers', 'backup_dependency', 'evidence'):
            text_list(entry[field])
        if (entry['sensitivity'] not in ('secret', 'private-metadata', 'public-key', 'ciphertext') or
                entry['category'] not in ('vault', 'state', 'archive') or
                entry['mode'] not in ('0600', '0644') or
                entry['sensitivity'] == 'secret' and entry['mode'] != '0600' or
                type(entry['required']) is not bool or
                entry['path_policy'] not in ('exact-bytes', 'rebase-checkout-paths', 'offline-inspection')):
            raise InventoryError('invalid file policy')
    if not isinstance(data['scan_roots'], list) or not data['scan_roots']:
        raise InventoryError('missing bounded discovery roots')
    roots = [exact_path(path) for path in data['scan_roots']]
    if len(roots) != len(set(roots)):
        raise InventoryError('duplicate discovery roots')
    if not isinstance(data['exclusions'], list):
        raise InventoryError('invalid exclusions')
    excluded_paths = set()
    for entry in data['exclusions']:
        if not isinstance(entry, dict) or set(entry) != {'path', 'kind', 'reason'}:
            raise InventoryError('invalid exclusion')
        path = exact_path(entry['path'])
        if path in excluded_paths or entry['kind'] not in ('file', 'tree'):
            raise InventoryError('duplicate or invalid exclusion')
        excluded_paths.add(path)
        text_field(entry['reason'])
        if path in paths or entry['kind'] == 'tree' and any(p.startswith(path + '/') for p in paths):
            raise InventoryError('exclusion hides inventoried file')
        if entry['kind'] == 'tree' and any(r == path or r.startswith(path + '/') for r in roots):
            raise InventoryError('discovery root enters excluded tree')
    if not isinstance(data['external_dependencies'], list) or not data['external_dependencies']:
        raise InventoryError('missing external recovery dependencies')
    for entry in data['external_dependencies']:
        if not isinstance(entry, dict) or set(entry) != {
                'id', 'owner', 'source', 'restore_destinations', 'sensitivity',
                'format', 'consumers', 'backup_dependency', 'rotation', 'status', 'evidence'}:
            raise InventoryError('invalid external dependency')
        if (not isinstance(entry['id'], str) or
                not re.fullmatch(r'[a-z][a-z0-9-]*', entry['id']) or entry['id'] in ids):
            raise InventoryError('invalid external dependency identity')
        ids.add(entry['id'])
        for field in ('owner', 'source', 'sensitivity', 'format', 'rotation'):
            text_field(entry[field])
        for field in ('restore_destinations', 'consumers', 'backup_dependency', 'evidence'):
            text_list(entry[field])
        if entry['status'] not in ('unverified', 'human-held', 'local-backup-only', 'planned'):
            raise InventoryError('invalid external dependency status')
    return data


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InventoryError('duplicate JSON field')
        result[key] = value
    return result


def load_manifest(path):
    try:
        # Resolve neither the leaf nor its parents through links. Opening with
        # NONBLOCK prevents a malicious FIFO from hanging before fstat checks it.
        path = Path(os.path.abspath(path))
        anchor = os.open(path.anchor, DIRECTORY_FLAGS)
        try:
            parent = open_directory(anchor, path.parts[1:-1])
        finally:
            os.close(anchor)
        try:
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        finally:
            os.close(parent)
        with os.fdopen(fd, 'rb') as stream:
            item = os.fstat(stream.fileno())
            if not stat.S_ISREG(item.st_mode) or item.st_size > 2_000_000:
                raise InventoryError('public manifest must be a bounded regular file')
            payload = stream.read(2_000_001)
            if len(payload) > 2_000_000:
                raise InventoryError('public manifest size limit exceeded')
        return validate_manifest(json.loads(payload, object_pairs_hook=no_duplicates))
    except (OSError, ValueError, TypeError, RecursionError):
        raise InventoryError('cannot parse public inventory manifest') from None


def open_directory(root_fd, parts):
    current = os.dup(root_fd)
    try:
        for part in parts:
            child = os.open(part, DIRECTORY_FLAGS, dir_fd=current)
            os.close(current)
            current = child
        return current
    except BaseException:
        os.close(current)
        raise


def metadata(root_fd, path):
    """Anchor each parent to a directory descriptor; never follow a symlink."""
    parts = PurePosixPath(path).parts
    parent = open_directory(root_fd, parts[:-1])
    try:
        return os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
    finally:
        os.close(parent)


def unsafe_parents(root_fd, path):
    current = os.dup(root_fd)
    try:
        for part in PurePosixPath(path).parts[:-1]:
            child = os.open(part, DIRECTORY_FLAGS, dir_fd=current)
            os.close(current)
            current = child
            item = os.fstat(current)
            if item.st_uid != os.getuid() or stat.S_IMODE(item.st_mode) & 0o022:
                return True
        return False
    finally:
        os.close(current)


def git_paths(root, paths):
    """Ignore/tracked status only; neither Git command reads private file data."""
    try:
        tracked = subprocess.run(['git', '-C', str(root), 'ls-files', '-z'],
                                 capture_output=True, check=True).stdout
        ignored = subprocess.run(['git', '-C', str(root), 'check-ignore', '--verbose', '-z', '--stdin'],
                                 input=b'\0'.join(os.fsencode(p) for p in paths) + b'\0',
                                 capture_output=True)
        if ignored.returncode not in (0, 1):
            raise InventoryError('Git ignore metadata unavailable')
    except (OSError, subprocess.CalledProcessError):
        raise InventoryError('Git path metadata unavailable') from None
    tracked_paths = {os.fsdecode(p) for p in tracked.split(b'\0') if p}
    records = ignored.stdout.split(b'\0')[:-1]
    if len(records) % 4:
        raise InventoryError('invalid Git ignore metadata')
    portable_ignored = set()
    for index in range(0, len(records), 4):
        source, _, pattern, path = (os.fsdecode(p) for p in records[index:index + 4])
        if source in tracked_paths and PurePosixPath(source).name == '.gitignore' and not pattern.startswith('!'):
            portable_ignored.add(path)
    sources = sorted({os.fsdecode(records[i]) for i in range(0, len(records), 4)
                      if os.fsdecode(records[i]) in tracked_paths})
    if sources:
        try:
            changed = subprocess.run(
                ['git', '-C', str(root), 'diff', 'HEAD', '--name-only', '-z', '--', *sources],
                capture_output=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            raise InventoryError('committed ignore metadata unavailable') from None
        changed_sources = {os.fsdecode(p) for p in changed.split(b'\0') if p}
        for index in range(0, len(records), 4):
            if os.fsdecode(records[index]) in changed_sources:
                portable_ignored.discard(os.fsdecode(records[index + 3]))
    return tracked_paths, portable_ignored


def discover(root_fd, manifest):
    """Inspect only named roots; excluded trees are never entered."""
    found, issues = set(), []
    exclusions = {e['path']: e['kind'] for e in manifest['exclusions']}
    visited = 0

    def visit(fd, prefix, depth):
        nonlocal visited
        if depth > 12:
            raise InventoryError('discovery depth limit exceeded')
        with os.scandir(fd) as entries:
            for entry in entries:
                visited += 1
                if visited > 2000:
                    raise InventoryError('bounded discovery file limit exceeded')
                path = prefix + '/' + entry.name
                try:
                    exact_path(path)
                    item = entry.stat(follow_symlinks=False)
                    kind = exclusions.get(path)
                    if stat.S_ISDIR(item.st_mode):
                        if kind == 'tree':
                            continue
                        child = os.open(entry.name, DIRECTORY_FLAGS, dir_fd=fd)
                        try:
                            visit(child, path, depth + 1)
                        finally:
                            os.close(child)
                    elif kind == 'file' and stat.S_ISREG(item.st_mode):
                        continue
                    else:
                        found.add(path)
                except (OSError, InventoryError):
                    issues.append({'code': 'discovery-entry-unsafe', 'path': prefix})

    for path in manifest['scan_roots']:
        try:
            fd = open_directory(root_fd, PurePosixPath(path).parts)
        except FileNotFoundError:
            continue
        except OSError:
            issues.append({'code': 'discovery-root-unsafe', 'path': path})
            continue
        try:
            visit(fd, path, 0)
        finally:
            os.close(fd)
    return found, issues


def check(root, manifest):
    manifest = validate_manifest(manifest)
    tracked, ignored = git_paths(root, [e['path'] for e in manifest['files']])
    rows, issues = [], []
    root = Path(os.path.abspath(root))
    anchor = os.open(root.anchor, DIRECTORY_FLAGS)
    try:
        root_fd = open_directory(anchor, root.parts[1:])
    finally:
        os.close(anchor)
    try:
        root_info = os.fstat(root_fd)
        if root_info.st_uid != os.getuid() or stat.S_IMODE(root_info.st_mode) & 0o022:
            issues.append({'code': 'unsafe-root-permissions', 'path': '.'})
        for entry in manifest['files']:
            path = entry['path']
            row = {'id': entry['id'], 'path': path, 'status': 'present'}
            if path in tracked:
                issues.append({'code': 'tracked-recovery-material', 'path': path})
            elif path not in ignored:
                issues.append({'code': 'not-repository-ignored', 'path': path})
            try:
                if unsafe_parents(root_fd, path):
                    issues.append({'code': 'unsafe-parent-permissions', 'path': path})
                item = metadata(root_fd, path)
                if not stat.S_ISREG(item.st_mode):
                    row['status'] = 'unsafe-type'
                    issues.append({'code': 'not-regular-file', 'path': path})
                else:
                    row.update(mode=f'{stat.S_IMODE(item.st_mode):04o}', bytes=item.st_size)
                    if item.st_nlink != 1:
                        issues.append({'code': 'hard-linked-file', 'path': path})
                    if item.st_uid != os.getuid():
                        issues.append({'code': 'unexpected-owner', 'path': path})
                    if stat.S_IMODE(item.st_mode) & ~int(entry['mode'], 8):
                        issues.append({'code': 'excess-permissions', 'path': path})
                    if item.st_size == 0:
                        issues.append({'code': 'empty-file', 'path': path})
            except FileNotFoundError:
                row['status'] = 'missing' if entry['required'] else 'optional-absent'
                if entry['required']:
                    issues.append({'code': 'missing-required-file', 'path': path})
            except OSError:
                row['status'] = 'unsafe-path'
                issues.append({'code': 'unsafe-or-inaccessible-path', 'path': path})
            rows.append(row)
        found, discovery_issues = discover(root_fd, manifest)
        issues.extend(discovery_issues)
        known = {entry['path'] for entry in manifest['files']}
        issues.extend({'code': 'unclassified-file', 'path': path} for path in sorted(found - known))
    finally:
        os.close(root_fd)
    return {'schema_version': 1, 'inventory_ok': not issues, 'deletion_safe': False,
            'files': rows, 'issues': issues,
            'external_dependencies': [{'id': e['id'], 'status': e['status']}
                                      for e in manifest['external_dependencies']],
            'scope': 'Metadata only; no secret contents, ciphertext, live services, or recovery verified.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--manifest', type=Path, default=MANIFEST)
    parser.add_argument('--manifest-only', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        if args.manifest_only:
            print('Recovery inventory schema valid; deletion safety NOT verified.')
            return 0
        result = check(args.root, manifest)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            counts = Counter(row['status'] for row in result['files'])
            print('Recovery inventory: ' + ', '.join(f'{n} {s}' for s, n in sorted(counts.items())))
            for issue in result['issues']:
                print(f"{issue['code']}: {issue['path']}")
            print(f"External dependencies: {len(result['external_dependencies'])}; see recovery/inventory.json.")
            print('Metadata only. Checkout deletion remains NOT SAFE; no recovery drill has run.')
        return 0 if result['inventory_ok'] else 1
    except (InventoryError, OSError):
        # Never render raw exception text or parser input; it may contain values.
        print('Recovery inventory check failed; inspect the public manifest and local path access.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
