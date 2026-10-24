#!/usr/bin/env python3
"""Human-only hidden entry of the DNS-scoped DreamHost ACME credential."""
import getpass
import os
import sys

from manage import PRIVATE


def main():
    if not sys.stdin.isatty():
        raise SystemExit('Run this recipe yourself in a terminal; never supply the key in chat or command arguments.')
    os.umask(0o077)
    directory = PRIVATE/'secrets'
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    path = directory/'dreamhost-api-key'
    if path.exists():
        raise SystemExit('A DNS key already exists; refusing an implicit credential replacement.')
    value = getpass.getpass('DreamHost key (DNS list/add/remove only; hidden): ').strip()
    if len(value) < 16 or any(character.isspace() for character in value):
        raise SystemExit('The key appears incomplete; nothing was saved.')
    with path.open('x') as stream: stream.write(value+'\n')
    path.chmod(0o600)
    print('Saved outside the checkout:', path)
    print('The next identity recovery archive will encrypt this credential with the existing master key.')


if __name__ == '__main__': main()
