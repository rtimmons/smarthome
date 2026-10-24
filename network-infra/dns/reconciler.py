"""Restart-free, crash-recoverable paired rule updates for automatic discovery."""
import json
import os
from pathlib import Path
import time


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w') as stream:
        os.chmod(temp, 0o600)
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def current_rules(client):
    status = client.api('filtering/status')
    if not status['enabled'] or not client.api('dns_info')['protection_enabled']:
        raise ValueError('Resolver filtering/protection disabled')
    if client.api('rewrite/list'):
        raise ValueError('Additional resolver rewrites require review')
    return status.get('user_rules', [])


def set_rules(client, rules):
    client.api('filtering/set_rules', {'rules': rules})
    client.api('cache_clear', {})
    if current_rules(client) != rules:
        raise ValueError('Rule readback differs')


def converge(clients, previous, candidate, directory, verify):
    """Clients are secondary then primary. Unknown rule drift is never overwritten.

    A pending journal permits recovery after death between API calls. A failed
    rollback retains it so the next run can reconcile either known generation.
    """
    directory = Path(directory)
    journal = directory / 'pending.json'
    if journal.exists():
        transaction = json.loads(journal.read_text())
        previous, candidate = transaction['previous'], transaction['candidate']
    before, after = previous['user_rules'], candidate['user_rules']
    actual = [current_rules(client) for client in clients]
    if any(value not in (before, after) for value in actual):
        raise ValueError('Unexpected custom-rule drift; automatic update paused')
    changed = before != after or actual != [after] * len(clients)
    if changed:
        atomic_json(journal, {'previous': previous, 'candidate': candidate})
        try:
            for client, value in zip(clients, actual):
                if current_rules(client) != value:
                    raise ValueError('Custom rules changed during reconciliation')
                if value != after:
                    set_rules(client, after)
            verify(candidate, previous)
        except Exception:
            restored = True
            for client in clients:
                try:
                    # Re-read before rollback: do not erase a concurrent manual edit.
                    value = current_rules(client)
                    if value not in (before, after):
                        restored = False
                    elif value != before:
                        set_rules(client, before)
                except Exception:
                    restored = False
            if restored:
                journal.unlink(missing_ok=True)
            raise
    atomic_json(directory / 'policy.json', candidate)
    journal.unlink(missing_ok=True)
    return candidate, changed
