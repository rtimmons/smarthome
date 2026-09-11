#!/usr/bin/env python3
"""Offline validation of the exact retained recovery inputs; never prints secrets."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tarfile
import tempfile
import threading
import uuid


MAX_BYTES = 512 * 1024**2
ENV = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C'}
CLOUD_RESOURCES = {'hcloud_ssh_key.admin', 'hcloud_primary_ip.ipv4', 'hcloud_primary_ip.ipv6',
                   'hcloud_firewall.server', 'hcloud_server.acquisition'}
STORAGE_RESOURCES = {'hcloud_storage_box.catalog', 'hcloud_storage_box_subaccount.qnap_reader'}
ARCHIVES = {
    'archive-cloud-20260910t214707z-nck4sdjo': 'cloud',
    'archive-cloud-20260910t223402z-zgjaggvx': 'cloud',
    'archive-cloud-20260910t224543z-ru5710kx': 'cloud',
    'archive-cloud-20260910t225152z-sifvfdwc': 'cloud',
    'archive-cloud-20260911t001750z-ucxzkhoy': 'cloud',
    'archive-cloud-vpn-20260911t005548': 'vpn',
    'archive-qnap-20260910t234609z-gr0zzbi0': 'qnap',
    'archive-unifi-network-20260911t004042z': 'unifi-network',
    'archive-unifi-system-20260911t004201z': 'unifi-system',
    'archive-usg-unifi-vpn-post-fix-20260911t173623': 'usg-post',
    'archive-usg-unifi-vpn-pre-fix-20260911t171125': 'usg-pre',
}
# Previously recorded source-byte evidence, not inferred from the ciphertext.
NATIVE_EXPORTS = {
    'unifi-network': (71344, '565f79f3b56eb17dc36249a9e82e4ff91257d18a0bee02627eceaa72bcca1062'),
    'unifi-system': (210752, '56b993411768f6727a474a2494c604d6698d9270d41dc7de5479c8fc31b056e3'),
}
KEY_IDS = ('cloud-admin', 'cloud-ui', 'qnap-admin', 'qnap-reader', 'storage-writer', 'ha-admin')


class ContentsError(Exception):
    pass


def _module(name):
    spec = importlib.util.spec_from_file_location('recovery_' + name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _hash(content):
    return hashlib.sha256(content).hexdigest()


def _json(content):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ContentsError('Duplicate JSON fields in recovery input.')
            result[key] = value
        return result
    return json.loads(content, object_pairs_hook=unique)


def _private_read(root, relative, mode='0600'):
    vault = _module('secrets-vault')
    root_fd = vault._root_fd(root)
    try:
        return vault._read_source(root_fd, relative, mode)
    finally:
        os.close(root_fd)


def _decrypt(content, root, age, kind):
    key = 'qnap-admin' if kind == 'qnap' else 'cloud-admin'
    identity = _private_read(root, 'usenet-infra/secrets/ssh/' + key)
    with tempfile.TemporaryDirectory(prefix='recovery-archive-check-') as temporary:
        work = Path(temporary)
        key_path, archive = work / 'identity', work / 'archive.age'
        for path, value in ((key_path, identity), (archive, content)):
            with path.open('xb') as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(value)
        with subprocess.Popen([str(age), '--decrypt', '--identity', str(key_path), str(archive)],
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              env=ENV, start_new_session=True) as process:
            def stop():
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            timer = threading.Timer(120, stop)
            timer.start()
            try:
                plaintext = process.stdout.read(MAX_BYTES + 1)
                if len(plaintext) > MAX_BYTES:
                    raise ContentsError('Archive exceeds the offline validation size limit.')
                if process.wait(timeout=10):
                    raise ContentsError('Retained archive authentication failed.')
                return plaintext
            finally:
                timer.cancel()
                if process.poll() is None:
                    stop()
                    process.wait()


def _terraform(identifier, content):
    if len(content) > 16 * 1024**2:
        raise ContentsError('Terraform state exceeds its size limit.')
    state = _json(content)
    if (not isinstance(state, dict) or type(state.get('version')) is not int or state['version'] != 4
            or type(state.get('serial')) is not int or state['serial'] < 0
            or not isinstance(state.get('lineage'), str) or not isinstance(state.get('resources'), list)):
        raise ContentsError('Terraform state schema is invalid.')
    uuid.UUID(state['lineage'])
    expected = STORAGE_RESOURCES if identifier == 'storage-tfstate' else CLOUD_RESOURCES
    addresses, resources, data_sources = set(), [], set()
    for resource in state['resources']:
        if not isinstance(resource, dict) or resource.get('mode') not in ('managed', 'data') or resource.get('module'):
            raise ContentsError('Terraform state contains an unexpected resource scope.')
        address = resource['type'] + '.' + resource['name']
        if resource['mode'] == 'data':
            if identifier == 'storage-tfstate' or address != 'hcloud_image.ubuntu' or address in data_sources:
                raise ContentsError('Terraform state contains an unexpected or duplicate data source.')
            data_sources.add(address)
            address = 'data.' + address
        else:
            if address not in expected or address in addresses:
                raise ContentsError('Terraform state contains an unexpected or duplicate resource.')
            addresses.add(address)
        instances = resource['instances']
        if (not isinstance(instances, list) or len(instances) != 1 or 'deposed' in instances[0]
                or 'index_key' in instances[0]):
            raise ContentsError('Terraform state resource instances are invalid.')
        resource_id = instances[0]['attributes']['id']
        if not isinstance(resource_id, (str, int)) or isinstance(resource_id, bool) or not re.fullmatch(r'[0-9]+(?:/[0-9]+)?', str(resource_id)):
            raise ContentsError('Terraform state resource identity is invalid.')
        resources.append([address, str(resource_id)])
    if identifier != 'cloud-prior-tfstate' and addresses != expected:
        raise ContentsError('Terraform state is missing required managed resources.')
    return {'kind': 'terraform-state', 'resources': len(addresses), 'data_sources': len(data_sources), 'serial': state['serial'],
            'lineage_sha256': _hash(state['lineage'].encode()),
            'resource_ids_sha256': _hash(json.dumps(sorted(resources), separators=(',', ':')).encode()),
            'validation': 'offline-schema-and-resource-identities; no live comparison or apply'}


def _usg(content, kind):
    paths = {'gateway-dump-cfg.json', 'unifi-usenet-cloud-ui.json'}
    if kind == 'usg-post':
        paths.add('config.gateway.json')
    scope = ('post' if kind == 'usg-post' else 'pre') + '-fix-usg-and-unifi-vpn'
    with tarfile.open(fileobj=io.BytesIO(content), mode='r:') as archive:
        members = []
        for member in archive:
            members.append(member)
            if len(members) > len(paths) + 1:
                raise ContentsError('USG archive exceeds its exact file-count limit.')
        names = [member.name for member in members]
        if (len(names) != len(set(names)) or set(names) != paths | {'MANIFEST.json'}
                or any(not m.isfile() or m.issparse() or m.size < 1 or m.size > 4 * 1024**2 for m in members)
                or archive.getmember('MANIFEST.json').size > 8192):
            raise ContentsError('USG archive violates its exact file allowlist.')
        manifest = _json(archive.extractfile('MANIFEST.json').read())
        if set(manifest) != {'scope', 'created_at', 'files'} or manifest['scope'] != scope:
            raise ContentsError('USG archive manifest is invalid.')
        entries = manifest['files']
        if not isinstance(entries, list) or len(entries) != len(paths) or {e['path'] for e in entries} != paths:
            raise ContentsError('USG archive manifest inventory is invalid.')
        for entry in entries:
            value = archive.extractfile(entry['path']).read()
            if (set(entry) != {'path', 'source_bytes', 'sha256'} or type(entry['source_bytes']) is not int
                    or len(value) != entry['source_bytes'] or _hash(value) != entry['sha256']):
                raise ContentsError('USG archive checksum verification failed.')
            if not isinstance(_json(value), (dict, list)):
                raise ContentsError('USG saved configuration is not structured JSON.')
    return {'kind': kind, 'files': len(paths), 'validation': 'authenticated-allowlisted-json-and-checksums'}


def _bounded_tar(content):
    # Legacy cloud extraction collects getmembers(); bound count first so an
    # authenticated but hostile tar cannot allocate an unbounded member list.
    with tarfile.open(fileobj=io.BytesIO(content), mode='r:') as archive:
        total = 0
        for count, member in enumerate(archive, 1):
            total += member.size
            if count > 25001 or total > MAX_BYTES or member.size < 0:
                raise ContentsError('Recovery archive exceeds bounded member limits.')


def validate_entry(entry: dict, content: bytes, root: Path, age: Path) -> dict:
    """Authenticate an exact inventory entry; return counts and hashes only.

    The caller must hash-verify the pinned age executable first. This function
    never runs Terraform, contacts a service, or installs a recovered file.
    """
    try:
        if not isinstance(content, bytes) or not 0 < len(content) <= MAX_BYTES:
            raise ContentsError('Recovery content size is invalid.')
        identifier = entry['id']
        if entry['category'] == 'state':
            if identifier in ('cloud-tfstate', 'storage-tfstate', 'cloud-prior-tfstate'):
                result = _terraform(identifier, content)
            elif identifier == 'zwave-historical-nvm':
                result = {'kind': 'historical-nvm', 'validation': 'opaque historical bytes only; not a current restore baseline'}
            else:
                raise ContentsError('Unsupported recovery state entry.')
        elif entry['category'] == 'archive' and identifier in ARCHIVES:
            kind = ARCHIVES[identifier]
            plaintext = _decrypt(content, root, age, kind)
            if kind == 'cloud':
                module = _module('config-backup')
                _bounded_tar(plaintext)
                with tempfile.TemporaryDirectory(prefix='recovery-cloud-check-') as temporary:
                    path = Path(temporary) / 'archive.tar'
                    with path.open('xb') as stream:
                        os.fchmod(stream.fileno(), 0o600)
                        stream.write(plaintext)
                    manifest = module.extract_verified(path, Path(temporary) / 'checked')
                    result = {'kind': kind, 'files': len(manifest['entries']),
                              'sqlite_databases': sum(bool(e['sqlite']) for e in manifest['entries']),
                              'validation': 'authenticated-allowlist-checksums-sqlite-integrity'}
            elif kind in ('vpn', 'qnap'):
                module = _module('backup-vpn' if kind == 'vpn' else 'backup-qnap')
                manifest = module.verify_tar(plaintext)
                result = {'kind': kind, 'files': len(manifest['files' if kind == 'vpn' else 'entries']),
                          'validation': 'authenticated-allowlist-and-checksums'}
            elif kind.startswith('usg-'):
                result = _usg(plaintext, kind)
            else:
                if (len(plaintext), _hash(plaintext)) != NATIVE_EXPORTS[kind]:
                    raise ContentsError('Native UniFi export differs from recorded source-byte evidence.')
                result = {'kind': kind, 'files': 1,
                          'validation': 'age-authentication-and-recorded-export-hash; native application restore unproven'}
        else:
            raise ContentsError('Unsupported recovery content entry.')
        return dict(result, sha256=_hash(content), size_bytes=len(content))
    except ContentsError:
        raise
    except Exception:
        raise ContentsError('Recovery content validation failed; no secret diagnostics were retained.') from None


def verify_keypairs(root: Path, manifest: dict) -> int:
    """Derive six public keys offline using copied private inputs and no agent."""
    try:
        entries = {e['id']: e for e in manifest['files']}
        with tempfile.TemporaryDirectory(prefix='recovery-keypair-check-') as temporary:
            for identifier in KEY_IDS:
                private, public = entries[identifier], entries[identifier + '-public']
                key = _private_read(root, private['restore_path'], private['mode'])
                expected = _private_read(root, public['restore_path'], public['mode']).split()
                path = Path(temporary) / 'identity'
                with path.open('wb') as stream:
                    os.fchmod(stream.fileno(), 0o600)
                    stream.write(key)
                result = subprocess.run(['/usr/bin/ssh-keygen', '-y', '-P', '', '-f', str(path)],
                                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                        env=ENV, timeout=10, check=True)
                actual = result.stdout.split()
                if len(expected) < 2 or len(actual) < 2 or actual[:2] != expected[:2]:
                    raise ContentsError('Restored SSH private/public keypair mismatch.')
        return len(KEY_IDS)
    except ContentsError:
        raise
    except Exception:
        raise ContentsError('Restored SSH keypair verification failed; no secret diagnostics were retained.') from None
