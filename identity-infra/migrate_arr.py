#!/usr/bin/env python3
"""Use the dedicated cloud connection for the scoped Prowlarr auth migration."""
import os
import subprocess
from manage import PRIVATE, ROOT


def main():
    os.umask(0o077)
    result = subprocess.run([str(ROOT/'usenet-infra/scripts/cloud-command'),'sudo','-n','python3','-'],
        input=(ROOT/'identity-infra/arr_auth_remote.py').read_bytes(),capture_output=True,timeout=150)
    (PRIVATE/'arr-auth-migration.log').write_bytes(result.stdout+result.stderr)
    if result.returncode:
        raise RuntimeError('Scoped Arr migration did not complete; inspect its private log')
    print('Prowlarr migration passed; API key, other settings and loopback binding preserved.')


if __name__=='__main__': main()
