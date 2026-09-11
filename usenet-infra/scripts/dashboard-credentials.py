#!/usr/bin/env python3
"""Create a private OliveTin local login without echoing or transmitting secrets.

Run with: uv run --with argon2-cffi==25.1.0 python scripts/dashboard-credentials.py
The resulting JSON is copied by Ansible as mode 0600; it contains only a hash.
"""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'secrets/dashboard-auth.json')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Credential file already exists. Select a new --output file to rotate credentials deliberately.')
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        parser.error("Run this command in an interactive terminal; refusing any password prompt without a private TTY.")
    from argon2 import PasswordHasher
    username = input('Dashboard username: ').strip()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', username):
        parser.error('Use a simple username of 1–64 letters, numbers, underscores, dots, or hyphens.')
    password = getpass.getpass('Dashboard password (at least 14 characters): ')
    if len(password) < 14 or password != getpass.getpass('Confirm dashboard password: '):
        parser.error('Passwords must match and contain at least 14 characters.')
    password_hash = PasswordHasher(time_cost=4, memory_cost=65536, parallelism=2).hash(password)
    del password
    args.output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump({'username': username, 'password_hash': password_hash}, stream)
        stream.write('\n')
    print('Saved the private dashboard authentication file. No password or hash was printed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
