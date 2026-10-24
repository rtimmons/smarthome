"""Download the verified off-host archive and independently decrypt/restore locally."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def main():
    os.umask(0o077)
    manager = module(ROOT / 'git-host/manage.py', 'git_manager')
    recon = module(ROOT / 'usenet-infra/scripts/qnap-recon.py', 'qnap_recon')
    connection = recon.connection_command(os.environ)
    command = manager.PRELUDE + '"$docker" exec usenet-backups-backups-1 cat /backups/forgejo/status.json\n'
    result = subprocess.run(connection, input=command.encode(), capture_output=True, check=True)
    status = json.loads(result.stdout)
    receipt = status['archive']
    if status['status'] != 'ok' or receipt.get('remote_ciphertext_verified') is not True:
        raise RuntimeError('no verified off-host archive')
    name = receipt['file']
    if not re.fullmatch(r'forgejo-\d{8}T\d{6}Z\.tar\.age', name):
        raise RuntimeError('invalid remote backup filename')
    directory = ROOT / 'build/git-host' / ('restore-' + str(time.time_ns()))
    directory.mkdir(mode=0o700, parents=True)
    ciphertext = directory / name
    command = manager.PRELUDE + '''"$docker" exec usenet-backups-backups-1 rclone \
--config /source/usenet/config/backup/offhost/rclone.conf cat nasbackup:archives/forgejo/''' + name + '\n'
    with ciphertext.open('xb') as output:
        result = subprocess.run(connection, input=command.encode(), stdout=output, stderr=subprocess.PIPE, timeout=3600)
    if result.returncode:
        raise RuntimeError('off-host archive download failed')
    with ciphertext.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != receipt['sha256']:
            raise RuntimeError('downloaded ciphertext differs from receipt')
    target = {'Darwin': 'darwin', 'Linux': 'linux'}[platform.system()]
    architecture = {'arm64': 'arm64', 'aarch64': 'arm64', 'x86_64': 'amd64'}[platform.machine()]
    age = ROOT / 'build/tools/age-1.3.2' / (target + '-' + architecture) / 'age'
    plaintext = directory / 'snapshot.tar'
    result = subprocess.run([str(age), '-d', '-i', os.environ['QNAP_SSH_KEY'], '-o', str(plaintext), str(ciphertext)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=3600)
    if result.returncode:
        raise RuntimeError('archive decryption failed')
    proof = module(ROOT / 'git-host/verify-backup.py', 'verify_forgejo').verify(plaintext, directory / 'restored')
    plaintext.unlink()
    proof.update({'source': 'Storage Box archives/forgejo', 'archive': name,
                  'ciphertext_sha256': receipt['sha256'], 'verified_at': int(time.time()),
                  'limit': 'File hashes, SQLite and Git objects verified; replacement-server startup not tested'})
    (directory / 'verification.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(proof))
    print('Private restore evidence: ' + str(directory))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
