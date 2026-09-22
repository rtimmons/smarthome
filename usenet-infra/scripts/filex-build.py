#!/usr/bin/env python3
"""Build the reviewed filex source plus the repository's narrow safety patch.

Does not deploy, update a running service, or change an accepted image pin.
The resulting binary and receipt are placed in the ignored build directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_SHA256 = 'd3efe9a117633b1f9e7999a226c18e7974669377d5577e29d40c739ec09076f9'
URL = 'https://api.github.com/repos/BRF-Tech/filex/tarball/v0.41.4'
VERSION = '0.41.4-smarthome.1'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def prepare(archive, destination):
    if digest(archive) != ARCHIVE_SHA256:
        raise ValueError('filex source archive checksum differs from the reviewed release')
    destination = Path(destination)
    destination.mkdir(exist_ok=False)
    with tarfile.open(archive) as bundle:
        members = bundle.getmembers()
        roots = {Path(m.name).parts[0] for m in members}
        if len(roots) != 1 or any(m.issym() or m.islnk() or not (m.isfile() or m.isdir())
                                 or '..' in Path(m.name).parts or Path(m.name).is_absolute()
                                 for m in members):
            raise ValueError('unexpected archive layout')
        bundle.extractall(destination, filter='data')
    source = destination / roots.pop()
    subprocess.run(['patch', '-p1', '--batch', '--fuzz=0', '-i', str(ROOT / 'patches/filex/safety.patch')],
                   cwd=source, check=True)
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    build = ROOT / 'build/filex'
    build.mkdir(parents=True, exist_ok=True)
    archive = args.archive or build / 'v0.41.4.tar.gz'
    if not archive.exists():
        with urllib.request.urlopen(URL, timeout=120) as response, archive.open('xb') as output:
            shutil.copyfileobj(response, output)
    workspace = Path(tempfile.mkdtemp(prefix='reviewed-', dir=build))
    source = prepare(archive, workspace / 'source')
    if args.prepare_only:
        print(json.dumps({'prepared_source': str(source)}))
        return
    go_version = subprocess.check_output(['go', 'version'], text=True).strip()
    if 'go1.27.1 ' not in go_version:
        raise ValueError('the reviewed build requires Go 1.27.1')
    env = {**os.environ, 'GOCACHE': str(build / 'go-cache'), 'GOMODCACHE': str(build / 'go-modules')}
    # Use the repository's pinned Node runtime and the upstream frozen lockfile.
    subprocess.run(['bash', '-c',
                    'set -euo pipefail; source "$1/talos/scripts/nvm_use.sh"; cd "$2"; '
                    'export CYPRESS_INSTALL_BINARY=0 NODE_OPTIONS=--max-old-space-size=4096; '
                    'npx --yes pnpm@9.12.0 install --frozen-lockfile; '
                    'npx --yes pnpm@9.12.0 audit --prod; '
                    'npx --yes pnpm@9.12.0 --filter ./web exec vitest run tests/operations/reconnect.test.ts; '
                    'npx --yes pnpm@9.12.0 run build; node scripts/sync-embed.mjs',
                    'filex-build', str(ROOT.parent), str(source)], cwd=ROOT.parent, check=True)
    backend = source / 'backend'
    subprocess.run(['go', 'test', './internal/ops', './internal/storage/drivers/local',
                    './internal/storage/drivers/sftp', './internal/trash', './internal/server', './internal/api/handlers'],
                   cwd=backend, env=env, check=True)
    with (workspace / 'go-vulnerability-scan.json').open('w') as output:
        subprocess.run(['go', 'run', 'golang.org/x/vuln/cmd/govulncheck@v1.1.4',
                        '-json', './cmd/filex'], cwd=backend, env=env, stdout=output, check=True)
    binary = workspace / 'filex'
    subprocess.run(['go', 'build', '-trimpath', '-ldflags',
                    '-s -w -X github.com/brf-tech/filex/backend/internal/version.Version=' + VERSION
                    + ' -X github.com/brf-tech/filex/backend/internal/version.Commit=56090d0',
                    '-o', str(binary), './cmd/filex'], cwd=backend,
                   env={**env, 'CGO_ENABLED': '0', 'GOOS': 'linux', 'GOARCH': 'amd64'}, check=True)
    shutil.copy2(ROOT / 'compose/filex/Dockerfile', workspace / 'Dockerfile')
    receipt = {'version': VERSION, 'source_archive_sha256': ARCHIVE_SHA256,
               'patch_sha256': digest(ROOT / 'patches/filex/safety.patch'),
               'binary_sha256': digest(binary), 'go': go_version,
               'node': (ROOT.parent / '.nvmrc').read_text().strip(), 'pnpm': '9.12.0'}
    (workspace / 'build-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'build_context': str(workspace), 'receipt': receipt}))


if __name__ == '__main__':
    main()
