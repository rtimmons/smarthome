#!/usr/bin/env python3
"""Human-only Gmail app-password entry, verified over TLS before saving."""
import getpass
import json
import os
import re
import smtplib
import ssl
import sys

from manage import PRIVATE


def main():
    if not sys.stdin.isatty():
        raise SystemExit('Run this recipe in your terminal. Never put the app password in chat or command arguments.')
    os.umask(0o077)
    directory = PRIVATE/'secrets'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory/'gmail-smtp.json'
    if path.exists():
        raise SystemExit('SMTP credentials already exist; refusing an implicit replacement.')
    username = input('Gmail sending address: ').strip()
    if not re.fullmatch(r'[A-Za-z0-9._%+-]+@(?:gmail|googlemail)\.com', username):
        raise SystemExit('Enter the Gmail account address associated with this app password.')
    password = ''.join(getpass.getpass('Google app password (16 characters; hidden): ').split())
    if not re.fullmatch(r'[a-z]{16}', password):
        raise SystemExit('The app password appears incomplete; nothing was saved.')
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ssl.create_default_context(), timeout=20) as client:
            client.login(username, password)
    except (OSError, smtplib.SMTPException):
        raise SystemExit('Gmail TLS authentication failed; nothing was saved. Check the account and app password.') from None
    with path.open('x') as stream:
        json.dump({'username': username, 'password': password}, stream)
        stream.write('\n')
    path.chmod(0o600)
    print('Gmail TLS authentication passed. Saved outside the checkout:', path)
    print('No email was sent. Deployment will enable Authelia notifications and encrypt this credential in recovery state.')


if __name__ == '__main__':
    main()
