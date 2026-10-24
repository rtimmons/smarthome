#!/usr/bin/env python3
"""Create the approved NAS users and write a private 1Password import file."""
import argparse
import csv
import json
import os
import secrets
import subprocess

from manage import PRIVATE, PRELUDE, ROOT, connection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email', required=True)
    args = parser.parse_args()
    if '@' not in args.email or any(c.isspace() for c in args.email):
        raise ValueError('Expected the approved account email')
    os.umask(0o077)
    path = PRIVATE/'human-logins.json'
    if path.exists():
        bootstrap = json.loads(path.read_text())
        if bootstrap['users'][0]['email'] != args.email:
            raise RuntimeError('Existing email differs; refusing an implicit account change')
    else:
        bootstrap = {'users': [
            {'username': 'ryantimmons', 'given_name': 'Ryan', 'surname': 'Timmons',
             'email': args.email, 'groups': ['nas-users', 'nas-timemachine', 'git-users', 'arr-users']},
            {'username': 'michaellee', 'given_name': 'Michael', 'surname': 'Lee',
             'groups': ['nas-users', 'nas-multimedia-writers']},
        ]}
        for user in bootstrap['users']:
            user['initial_password'] = secrets.token_urlsafe(36)
        with path.open('x') as stream:
            json.dump(bootstrap, stream, indent=2)
            stream.write('\n')
    script = 'bootstrap = '+repr(bootstrap)+'\n'+(ROOT/'identity-infra/household_users.py').read_text()
    marker = PRIVATE/'ha-cutover.json'
    if marker.exists():
        if json.loads(marker.read_text()).get('phase') not in ('activated', 'verified'):
            raise RuntimeError('Directory cutover is incomplete; refusing account operations')
        from ha_directory import execute
        result = execute(('python3 - <<\'USERS\'\n'+script+'\nUSERS\n').encode())
    else:
        remote = PRELUDE+'"$docker" exec -i home-identity-dc-1 python3 - <<\'USERS\'\n'+script+'\nUSERS\n'
        result = subprocess.run(connection(), input=remote.encode(), capture_output=True, timeout=120)
    (PRIVATE/'create-users.log').write_bytes(result.stdout+result.stderr)
    if result.returncode:
        raise RuntimeError('User creation failed; inspect private log. Existing passwords were not reset.')
    export = PRIVATE/'household-logins.1password.csv'
    with export.open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['Title', 'Username', 'Password', 'Website', 'Notes'])
        for user in bootstrap['users']:
            writer.writerow(['Smarthome AD - '+user['given_name'], 'SMARTHOME\\'+user['username'],
                             user['initial_password'],
                             'https://auth.home.rytim.com' if 'git-users' in user['groups'] else '',
                             'SMB domain: SMARTHOME. Browser username: '+user['username']+
                             '. Initial migration password; existing local NAS password is unchanged.'])
    print('Household identities verified. Private 1Password import:', export)
    print('No credentials printed. Existing local NAS users and share access remain unchanged.')


if __name__ == '__main__':
    main()
