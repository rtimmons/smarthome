#!/usr/bin/env python3
"""Rebuild a recovery checkout from Git, one supplied master, and the QNAP store.

Git authentication is an external operator prerequisite. No original ignored
files, tool caches or service credentials are copied into the new checkout.
This drill never starts applications or applies state to production services.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = 'git@github.com:rtimmons/smarthome.git'
BRANCH = 'usenet'
RELEVANT = ('.sops.yaml', '.gitignore', 'AGENTS.md', 'Justfile', 'plan.md', 'usenet-infra')
REVISION = re.compile(r'[a-f0-9]{40}(?:[a-f0-9]{24})?')
SNAPSHOT = re.compile(r'[0-9]{8}T[0-9]{6}Z-[a-f0-9]{16}')


class DrillError(RuntimeError):
    """Only fixed stage names and sanitized reports cross the CLI boundary."""


def child_environment(environ):
    result = {'PATH': os.defpath, 'LANG': 'C', 'LC_ALL': 'C', 'GIT_TERMINAL_PROMPT': '0'}
    # Git alone may use the operator's configured credential helper/SSH agent.
    # No cloud, SOPS, age, shell-injection or arbitrary Git environment survives.
    for name in ('HOME', 'SSH_AUTH_SOCK'):
        if environ.get(name):
            result[name] = environ[name]
    return result


def run(command, *, cwd, env, runner=subprocess.run, timeout=120):
    try:
        result = runner(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        raise DrillError('child-command') from None
    if result.returncode:
        raise DrillError('child-command')
    return result.stdout


def git(root, arguments, env, runner):
    return run(['/usr/bin/git', '-c', 'core.hooksPath=/dev/null', *arguments],
               cwd=root, env=env, runner=runner)


def committed_revision(root, env, runner):
    revision = git(root, ['rev-parse', '--verify', 'HEAD'], env, runner).decode('ascii').strip()
    if not REVISION.fullmatch(revision):
        raise DrillError('source-revision')
    status = git(root, ['status', '--porcelain=v1', '-z', '--untracked-files=all', '--', *RELEVANT], env, runner)
    if status:
        raise DrillError('uncommitted-recovery-source')
    return revision


def load_module(root, name):
    path = root / 'usenet-infra/scripts' / (name + '.py')
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise DrillError('fresh-source-module')
    spec = importlib.util.spec_from_file_location('cold_drill_' + name.replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_request(snapshot, source, destination, root):
    if not SNAPSHOT.fullmatch(snapshot):
        raise DrillError('snapshot-id')
    # A local clone can silently share/copy object databases or ignored state;
    # require an actual remote Git source with no embedded HTTP password/token.
    if not (re.fullmatch(r'git@[A-Za-z0-9.-]+:[A-Za-z0-9_./-]+\.git', source)
            or re.fullmatch(r'https://[A-Za-z0-9.-]+/[A-Za-z0-9_./-]+\.git', source)
            or re.fullmatch(r'ssh://git@[A-Za-z0-9.-]+/[A-Za-z0-9_./-]+\.git', source)):
        raise DrillError('remote-git-source')
    if not destination.is_absolute() or destination.exists() or destination.is_symlink():
        raise DrillError('new-absolute-destination')
    if destination.resolve().is_relative_to(root.resolve()):
        raise DrillError('destination-inside-source')
    parent = destination.parent.stat()
    if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.getuid() or parent.st_mode & 0o022:
        raise DrillError('destination-parent-permissions')


def write_report(root, report):
    build = root / 'build'
    if build.is_symlink():
        raise DrillError('report-directory')
    build.mkdir(mode=0o700, exist_ok=True)
    destination = build / 'recovery-drill.json'
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
        json.dump(report, stream, sort_keys=True, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(build, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return destination


def count(value):
    if type(value) is not int or value < 0:
        raise DrillError('invalid-verification-result')
    return value


def drill(snapshot, destination, *, source=SOURCE, expected_revision=None, root=ROOT,
          environ=None, runner=subprocess.run, module_loader=load_module):
    environ = os.environ if environ is None else environ
    # Remove the master before Git, bootstrap, imports or any other child work.
    identity = environ.pop('SOPS_AGE_KEY', None)
    os.environ.pop('SOPS_AGE_KEY', None)
    if not identity or not identity.startswith('AGE-SECRET-KEY-1') or '\x00' in identity:
        raise DrillError('master-input')
    destination, root = Path(destination), Path(root)
    validate_request(snapshot, source, destination, root)
    env = child_environment(environ)
    stage, created = 'source-commit-gate', False
    report = {'schema_version': 1, 'snapshot_id': snapshot, 'status': 'failed',
              'deletion_safe': False, 'application_startup_repeated': False,
              'unifi_native_restore_supported': False}
    try:
        revision = committed_revision(root, env, runner)
        if expected_revision is not None and expected_revision != revision:
            raise DrillError('expected-revision-mismatch')
        report['source_revision'] = revision
        stage = 'git-clone'
        destination.mkdir(mode=0o700)
        created = True
        git(root, ['-c', 'init.templateDir=', '-c', 'protocol.file.allow=never', 'clone',
                   '--no-local', '--no-hardlinks', '--single-branch', '--branch', BRANCH,
                   '--', source, str(destination)], env, runner)
        stage = 'clone-revision-gate'
        cloned_revision = committed_revision(destination, env, runner)
        if cloned_revision != revision or committed_revision(root, env, runner) != revision:
            raise DrillError('clone-revision-mismatch')
        stage = 'cold-checkout-gate'
        checker = module_loader(destination, 'secrets-check')
        infra = destination / 'usenet-infra'
        manifest_path = infra / 'recovery/inventory.json'
        manifest = checker.load_manifest(manifest_path)
        if (os.path.lexists(destination / 'build')
                or any(os.path.lexists(destination / entry['path']) for entry in manifest['files'])):
            raise DrillError('preexisting-recovery-material')
        stage = 'pinned-public-bootstrap'
        bootstrap_env = {'PATH': os.defpath, 'LANG': 'C', 'LC_ALL': 'C'}
        for script in ('bootstrap-age.py', 'bootstrap-sops.py'):
            run([sys.executable, '-I', str(infra / 'scripts' / script)], cwd=destination,
                env=bootstrap_env, runner=runner, timeout=300)
        stage = 'vault-restore'
        vault = module_loader(destination, 'secrets-vault')
        vault_count = count(vault.restore(destination, manifest_path, infra / 'vault/secrets.sops.json',
                                         environ={'SOPS_AGE_KEY': identity}))
        stage = 'qnap-download'
        store = module_loader(destination, 'recovery-store')
        connection = store.connection_command(store.read_environment(infra / '.env'))
        downloaded = destination / 'build/recovery-download'
        store.fetch(snapshot, downloaded, connection)
        stage = 'bundle-restore-and-verify'
        bundle = module_loader(destination, 'recovery-bundle')
        first = bundle.verify(destination, downloaded, identity=identity, restore=True)
        if first.get('master_decryption_verified') is not True or first.get('snapshot_id') != snapshot:
            raise DrillError('unauthenticated-result')
        stage = 'idempotent-restore-and-verify'
        second = bundle.verify(destination, downloaded, identity=identity, restore=True)
        if (second.get('master_decryption_verified') is not True or second.get('snapshot_id') != snapshot
                or count(second.get('new_files_restored')) != 0
                or count(second.get('entries')) != count(first.get('entries'))
                or count(second.get('keypairs_verified')) != count(first.get('keypairs_verified'))):
            raise DrillError('non-idempotent-result')
        stage = 'restored-metadata-check'
        metadata = checker.check(destination, manifest)
        if metadata.get('inventory_ok') is not True:
            raise DrillError('restored-metadata-invalid')
        report.update(status='verified', fresh_clone=True, official_pinned_tools_bootstrapped=True,
                      vault_entries_restored=vault_count, bundle_entries_verified=count(first.get('entries')),
                      keypairs_verified=count(first.get('keypairs_verified')),
                      first_pass_new_files=count(first.get('new_files_restored')),
                      second_pass_new_files=0, master_decryption_verified=True, inventory_ok=True,
                      completed_at=datetime.now(timezone.utc).isoformat())
        stage = 'report-publication'
        return write_report(destination, report), report
    except Exception:
        if created:
            try:
                write_report(destination, {**report, 'status': 'failed', 'failed_stage': stage})
            except Exception:
                pass
        raise DrillError(stage) from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True)
    parser.add_argument('--destination', required=True, type=Path)
    parser.add_argument('--source', default=SOURCE)
    parser.add_argument('--expected-revision')
    args = parser.parse_args(argv)
    try:
        path, report = drill(args.snapshot, args.destination, source=args.source,
                             expected_revision=args.expected_revision)
        print('Clean-clone recovery verified: ' + str(report['vault_entries_restored']) + ' vault entries, '
              + str(report['bundle_entries_verified']) + ' bundle entries, '
              + str(report['keypairs_verified']) + ' keypairs; repeat restored 0 new files.')
        print('Report: ' + str(path))
        print('Application startup was not repeated; UniFi native restore remains unsupported. Deletion safety is not established.')
        return 0
    except DrillError as exc:
        print('Recovery drill failed at ' + str(exc) + '; any created clone was preserved for diagnosis.', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Recovery drill interrupted; temporary plaintext was cleaned up and the clone was preserved.', file=sys.stderr)
        return 130
    except Exception:
        print('Recovery drill failed validation; any created clone was preserved for diagnosis.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    raise SystemExit(main())
