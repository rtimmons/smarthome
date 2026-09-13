#!/usr/bin/env python3
"""OliveTin presentation adapter. Storage operations belong to the catalog and native-library backends.

Generated YAML is JSON (a YAML subset), never concatenated untrusted YAML. Action
IDs contain the immutable catalog ID, not an entity array index. A stale browser
cannot accidentally act on the item now occupying another item's row.
"""
from __future__ import annotations

import argparse
import fcntl
import html
import ipaddress
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

import catalogctl

SCRIPT = Path(__file__).resolve()
BACKEND = SCRIPT.with_name('catalogctl.py')
NATIVE_BACKEND = SCRIPT.with_name('native_library.py')
STATES = {'remote_only': 'remote only', 'downloading': 'downloading', 'local': 'local', 'failed': 'failed'}
ALLOWED_ACTIONS = {'remote_only': {'download', None}, 'local': {'evict', None}, 'failed': {'retry', 'evict', None}, 'downloading': {None}}


def root() -> Path:
    return Path(os.environ.get('CATALOG_DASHBOARD_ROOT', '/data/dashboard'))


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text() == content:
        return
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def escaped(value: object) -> str:
    return html.escape(str(value), quote=True).replace("{", "&#123;").replace("}", "&#125;")


def bytes_label(value: object) -> str:
    return catalogctl.human_bytes(int(value or 0))


def backend_snapshot(backend: Path) -> dict:
    timeout = int(os.environ.get('CATALOG_DASHBOARD_SNAPSHOT_TIMEOUT', '120'))
    if timeout < 1:
        raise ValueError('Catalog snapshot timeout must be positive.')
    process = subprocess.Popen([sys.executable, str(backend), 'status', '--json'],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException as exc:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()
        if isinstance(exc, subprocess.TimeoutExpired):
            raise catalogctl.CatalogError(f'Catalog refresh exceeded {timeout} seconds; check Storage Box connectivity.') from exc
        raise
    if process.returncode:
        raise catalogctl.CatalogError(stderr.strip() or 'Catalog status failed')
    return json.loads(stdout)


def snapshot() -> dict:
    legacy = backend_snapshot(BACKEND)
    # Presentation updates may precede the separate native-library rollout.
    if not NATIVE_BACKEND.is_file():
        return legacy
    native = backend_snapshot(NATIVE_BACKEND)
    merged = dict(legacy)
    merged['items'] = [dict(item, source='legacy') for item in legacy.get('items', [])] + [
        dict(item, source='native') for item in native.get('items', [])]
    for key in ('remote_items', 'remote_bytes', 'local_items', 'local_bytes',
                'transfers_in_progress', 'stalled_transfers', 'failed_transfers'):
        merged[key] = int(legacy.get(key, 0)) + int(native.get(key, 0))
    # The legacy snapshot already counts the shared failure journal.
    # Both sources share a volume and reserve; these values must not be added.
    merged['local_free_bytes'] = min(int(legacy.get('local_free_bytes', 0)),
                                     int(native.get('local_free_bytes', 0)))
    merged['local_reserve_bytes'] = max(int(legacy.get('local_reserve_bytes', 0)),
                                        int(native.get('local_reserve_bytes', 0)))
    return merged


def item_source(item: dict) -> str:
    source = item.get('source', 'legacy')
    # Old persisted snapshots contain the manifest's provenance object here.
    # New combined snapshots replace that field with a backend discriminator.
    if isinstance(source, dict):
        source = 'legacy'
    if source not in ('legacy', 'native'):
        raise ValueError('Unknown catalog source')
    return source


def command_args(*args: str) -> list[str]:
    return [sys.executable, str(SCRIPT), *args]


def transfer_panel(data: dict, refresh_error: str | None) -> dict:
    rows = [i for i in data.get('items', []) if (i.get('operation') or {}).get('operation') in ('pull', 'native-pull')]
    active = [i for i in rows if i['operation'].get('active')]
    recent = sorted(rows, key=lambda i: i['operation'].get('updated_at', ''), reverse=True)[:1]
    # Ship layout with the authenticated dashboard data as well as custom JS:
    # browsers can retain OliveTin's unversioned custom.js across an upgrade.
    body = ('<style>fieldset:has(.transfer-status){display:block;width:auto;max-width:960px;margin-inline:auto}'
            '.dashboard-row:has(.transfer-status) .display{width:100%;padding:24px;box-sizing:border-box}'
            '.dashboard-row:has(.transfer-status) .display>div{width:100%;min-width:0}'
            '.transfer-status{overflow-wrap:anywhere}</style>'
            '<div class="transfer-status" style="text-align:left;min-width:0">')
    if refresh_error:
        body += '<h2>Download status unavailable · Cloud → NAS</h2>'
        body += '<p><strong>Status unavailable — last known values below.</strong></p>'
    else:
        body += f'<h2>{len(active)} active download{"s" if len(active) != 1 else ""} · Cloud → NAS</h2>' if active else '<h2>No active downloads · Cloud → NAS</h2>'
    for row in active or recent:
        operation = row['operation']
        live = bool(operation.get('active')) and not refresh_error
        phase = operation.get('phase', 'Preparing')
        copying = live and ('downloading' in phase or 'copying' in phase)
        progress = operation.get('progress') or {}
        fresh = copying and 0 <= time.time() - progress.get('at', 0) <= 45
        rate = bytes_label(progress.get('speed')) + '/s' if fresh else ('Waiting for speed data' if copying else '—')
        label = phase if live else operation.get('status', 'unknown')
        body += f'<h3>{escaped(row["title"])}</h3><p><strong>{escaped(label)}</strong></p>'
        stamp = f' data-speed-at="{progress["at"]}"' if fresh else ''
        body += f'<div{stamp} style="font-size:2em;font-weight:700">{rate}</div>'
        if progress:
            total = progress.get('total_bytes', 0)
            copied = progress.get('bytes', 0)
            percentage = min(100, 100 * copied / total) if total else 0
            body += f'<p>{bytes_label(copied)} / {bytes_label(total)} transferred this attempt'
            if total:
                body += f' · {percentage:.1f}%'
            if fresh and progress.get('eta') is not None:
                body += f' · about {max(1, round(progress["eta"] / 60))} min remaining'
            body += '</p>'
            if total:
                body += f'<progress style="width:100%" max="100" value="{percentage:.1f}" aria-label="Transfer progress">{percentage:.1f}%</progress>'
        history = operation.get('speed_history', [])[-60:]
        if history:
            peak = max(p['speed'] for p in history)
            start, end = history[0]['at'], history[-1]['at']
            span = max(10, end - start)
            body += f'<p><strong>Download speed history</strong> · peak {bytes_label(peak)}/s</p>'
            body += '<div role="img" aria-label="Download speed over time, oldest to newest" style="position:relative;height:80px;border-bottom:1px solid currentColor;margin:12px 0">'
            for point in history:
                left = 98 * (point['at'] - start) / span
                height = max(1, round(76 * point['speed'] / peak)) if peak else 1
                hint = f'{round(point["at"] - start)}s: {bytes_label(point["speed"])}/s'
                body += f'<span title="{hint}" style="position:absolute;bottom:0;left:{left:.2f}%;width:1.6%;min-width:2px;height:{height}px;background:#20a5a0"></span>'
            body += f'</div><p><small>{round(end - start)} seconds of history · oldest → newest · samples about every 10s</small></p>'
        else:
            body += '<p>Speed history starts with downloads launched after this update.</p>'
        if live and not copying:
            body += '<p>Preparation and verification can take time; network speed is shown during copying.</p>'
        if operation.get('error'):
            body += f'<p>{escaped(operation["error"])}</p>'
    if not rows:
        body += '<p>Select Download on a title below. Its speed and history will appear here.</p>'
    body += '<p><small>Updates automatically. Transfer completion is followed by verification and Plex discovery.</small></p></div>'
    return {'type': 'fieldset', 'title': 'Downloads', 'contents': [{'type': 'display', 'title': body}]}


def dashboard_config(data: dict, refresh_error: str | None = None) -> dict:
    """Return declarative actions/cards; metadata is never executable markup."""
    actions = [{
        'id': 'catalog-refresh', 'title': 'Refresh catalog', 'icon': '⟳',
        'exec': command_args('refresh'), 'timeout': 300, 'maxConcurrent': 1,
        'popupOnStart': 'execution-dialog',
    }]
    summary = (
        f'<strong>Listed remote titles:</strong> {int(data.get("remote_items", 0))} items · {bytes_label(data.get("remote_bytes"))}<br>'
        f'<strong>Local:</strong> {int(data.get("local_items", 0))} items · {bytes_label(data.get("local_bytes"))}<br>'
        f'<strong>Available NAS space:</strong> {bytes_label(data.get("local_free_bytes"))}'
        f' · <strong>Reserve:</strong> {bytes_label(data.get("local_reserve_bytes"))}<br>'
        f'<strong>Running:</strong> {int(data.get("transfers_in_progress", 0))}'
        f' · <strong>Stalled:</strong> {int(data.get("stalled_transfers", 0))}'
        f' · <strong>Recorded failures:</strong> {int(data.get("recorded_failures", 0))}<br>'
        f'<small>Native and legacy entries can refer to the same canonical bytes.</small><br>'
        f'<small>Updated: {escaped(data.get("generated_at", "Awaiting first refresh"))}</small>'
    )
    if refresh_error:
        summary += f'<p><strong>Catalog refresh failed. Values may be stale; actions are disabled.</strong><br>{escaped(refresh_error)}</p>'
    contents = [transfer_panel(data, refresh_error), {'type': 'fieldset', 'title': 'Capacity and activity', 'contents': [
        {'type': 'display', 'title': summary}, {'title': 'Refresh catalog'},
        {'type': 'display', 'title': 'This catalog updates automatically. Use the top search box for title or category. The Entities view also provides a filterable catalog table. Execution logs retain status and output; downloads continue when this browser closes.'},
    ]}]
    seen = set()
    for item in sorted(data.get('items', []), key=lambda i: (i['title'].casefold(), i['id'])):
        item_id = catalogctl.safe_id(item['id'])
        source = item_source(item)
        identity = (source, item_id)
        if identity in seen:
            raise ValueError('duplicate catalog ID')
        seen.add(identity)
        state = item['state']
        if item['valid_action'] not in ALLOWED_ACTIONS[state]:
            raise ValueError('catalog state/action mismatch')
        title = escaped(item['title'])
        category = escaped(item['category'])
        source_label = 'Native library' if source == 'native' else 'Legacy catalog'
        details = f'<strong>{category}</strong> · {source_label} · {bytes_label(item["size_bytes"])} · <strong>{STATES[state]}</strong>'
        if item.get('error'):
            details += f'<p>{escaped(item["error"])}</p>'
        card = {'type': 'fieldset', 'title': title, 'contents': [{'type': 'display', 'title': details}]}
        verb = None if refresh_error else item['valid_action']
        if verb:
            label = {'download': 'Download', 'retry': 'Retry', 'evict': 'Remove local copy'}[verb]
            # A unique title is required by OliveTin dashboard linking. Include
            # category for native search, and the ID for unambiguous audit logs.
            action_title = f'{label} · {title} · {category} · {source_label} [{item_id}]'
            action = {
                'id': f'{"native" if source == "native" else "catalog"}-{verb}-{item_id}', 'title': action_title,
                'exec': command_args('action', verb, item_id),
                'timeout': 2592000,  # 30 days: finite but sufficient for large pulls.
                'maxConcurrent': 1, 'popupOnStart': 'execution-dialog',
                'icon': '⬇' if verb != 'evict' else '⊖',
            }
            if source == 'native':
                action['exec'] += ['--source', 'native']
            if verb == 'evict':
                action['arguments'] = [{
                    'name': 'confirm', 'type': 'confirmation',
                    'title': 'Remove only this QNAP local copy. The canonical remote copy will remain.',
                }]
                action['exec'] += ['--confirm', '{{ .Arguments.confirm }}']
            actions.append(action)
            card['contents'].append({'title': action_title})
        contents.append(card)
    if not data.get('items'):
        contents.append({'type': 'display', 'title': 'No catalog items are available yet. Refresh after a native library import or legacy publication.'})
    return {'actions': actions, 'dashboards': [{'title': 'Catalog', 'acls': ['catalog-operators'], 'contents': contents}]}


def publish(data: dict, error: str | None = None) -> None:
    config = dashboard_config(data, error)
    refresh_script = SCRIPT.with_name('catalog-refresh.js')
    if refresh_script.is_file():
        atomic_write(root() / 'runtime/custom-webui/custom.js', refresh_script.read_text())
    entities = [{
        'id': f'{item_source(i)}-{i["id"]}', 'title': f'{i["title"]} · {i["category"]}', 'item_title': i['title'], 'category': i['category'],
        'size': bytes_label(i['size_bytes']), 'state': STATES[i['state']],
        'error': i.get('error') or '', 'source': item_source(i),
    } for i in data.get('items', [])]
    atomic_write(root() / 'catalog.json', ''.join(json.dumps(i) + '\n' for i in entities))
    atomic_write(root() / 'generated' / 'catalog.yaml', json.dumps(config, indent=2) + '\n')
    template = Path(os.environ.get('CATALOG_DASHBOARD_CONFIG_TEMPLATE', '/opt/usenet/olivetin/config.yaml'))
    if template.exists():
        base = json.loads(template.read_text())
        base.update(config)
        # OliveTin watches only its primary config, not included config files.
        # Auth remains placeholders sourced from the private environment.
        atomic_write(root() / 'runtime' / 'config.yaml', json.dumps(base, indent=2) + '\n')
    atomic_write(root() / 'status.json', json.dumps({'updated_at': time.time(), 'error': error, 'snapshot': data}))


def refresh() -> bool:
    root().mkdir(parents=True, exist_ok=True)
    with (root() / 'refresh.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            data = snapshot()
            publish(data)
            return True
        except (catalogctl.CatalogError, OSError, ValueError, KeyError) as exc:
            old = root() / 'status.json'
            try:
                data = json.loads(old.read_text()).get('snapshot', {}) if old.exists() else {}
            except (OSError, ValueError):
                data = {}
            publish(data, str(exc))
            print(f'Catalog refresh failed: {exc}', file=sys.stderr, flush=True)
            return False


def perform_action(verb: str, item_id: str, confirm: str | None, source: str = 'legacy') -> int:
    catalogctl.safe_id(item_id)
    item_source({'source': source})
    if verb == 'evict' and confirm != '1':
        raise ValueError('Confirm that only the QNAP copy is removed; the remote copy remains.')
    # Re-resolve the canonical listing, and validate source and state again. This
    # deliberately refuses a stale tab's Download/Retry/Remove operation.
    data = snapshot()
    matches = [i for i in data['items'] if i['id'] == item_id and item_source(i) == source]
    if len(matches) != 1 or matches[0]['valid_action'] != verb:
        raise ValueError('The item state changed. Refresh the catalog and select its current action.')
    print(f'{verb}: {item_id}. Verification and catalog safeguards are active.', flush=True)
    if verb == 'evict':
        print('Removing the QNAP copy only. The canonical remote copy will remain.', flush=True)
    # OliveTin owns this process group. A browser disconnect does not stop it;
    # timeout/container shutdown kills the group, and catalog locks expose any
    # interrupted pull as retryable rather than leaving an orphaned transfer.
    backend = NATIVE_BACKEND if source == 'native' else BACKEND
    process = subprocess.Popen([sys.executable, '-u', str(backend), 'evict' if verb == 'evict' else 'pull', item_id])
    # Refresh once the backend has created its operation record, then at a
    # bounded interval while streaming rclone output to OliveTin execution logs.
    while True:
        try:
            result = process.wait(timeout=2 if verb == 'evict' else 5)
            break
        except subprocess.TimeoutExpired:
            refresh()
            print('Transfer is still running; execution output and catalog state remain available.', flush=True)
            try:
                result = process.wait(timeout=25)
                break
            except subprocess.TimeoutExpired:
                pass
    refresh()
    return result


def load_auth(path: Path) -> dict[str, str]:
    if path.stat().st_mode & 0o077:
        raise ValueError('Dashboard authentication file must have mode 0600.')
    auth = json.loads(path.read_text())
    username = auth.get('username', '')
    password_hash = auth.get('password_hash', '')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', username):
        raise ValueError('Dashboard username must be a simple 1–64 character identifier.')
    if not re.fullmatch(r'\$argon2id\$v=19\$m=\d+,t=\d+,p=\d+\$[A-Za-z0-9+/]+\$[A-Za-z0-9+/]+', password_hash):
        raise ValueError('Dashboard requires an Argon2id password hash; no plaintext passwords.')
    return {'CATALOG_DASHBOARD_USERNAME': username, 'CATALOG_DASHBOARD_PASSWORD_HASH': password_hash}


def healthcheck() -> int:
    state = json.loads((root() / 'status.json').read_text())
    maximum_age = max(180, int(os.environ.get('CATALOG_DASHBOARD_REFRESH_SECONDS', '60')) * 3 + 300)
    if time.time() - state['updated_at'] > maximum_age or state['error']:
        raise ValueError('Catalog refresh failed or stopped; inspect dashboard capacity panel and logs.')
    with urllib.request.urlopen('http://127.0.0.1:1337/readyz', timeout=5) as response:
        if response.status != 200:
            raise ValueError('OliveTin is not ready')
    return 0


def sanitized_log(line: str, password_hash: str) -> str | None:
    try:
        if json.loads(line).get('level', '').lower() in ('debug', 'trace'):
            return None
    except (ValueError, AttributeError):
        if 'level="debug"' in line or 'level="trace"' in line:
            return None
    return line.replace(password_hash, '[redacted]')


def serve() -> int:
    os.umask(0o077)
    bind = ipaddress.ip_address(os.environ.get('CATALOG_DASHBOARD_BIND_ADDRESS', '127.0.0.1'))
    if bind.version != 4 or not (bind.is_loopback or any(bind in ipaddress.ip_network(cidr) for cidr in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))):
        raise ValueError('Dashboard bind must be an approved private LAN IPv4 address or loopback.')
    template = Path(os.environ.get('CATALOG_DASHBOARD_CONFIG_TEMPLATE', '/opt/usenet/olivetin/config.yaml'))
    if not template.is_file():
        raise ValueError('The read-only dashboard configuration template is missing.')
    auth = load_auth(Path(os.environ.get('CATALOG_DASHBOARD_AUTH_FILE', '/run/secrets/dashboard-auth.json')))
    for directory in ('generated', 'runtime', 'logs/results', 'logs/output'):
        (root() / directory).mkdir(parents=True, exist_ok=True)
    # Fail closed on missing credentials, but keep an authenticated error page
    # available when Storage Box is down during startup.
    try:
        cached = json.loads((root() / 'status.json').read_text()).get('snapshot', {})
    except (OSError, ValueError):
        cached = {}
    publish(cached, 'Refreshing the catalog; the private dashboard is ready while Storage Box is checked.')
    stop = threading.Event()
    interval = max(15, int(os.environ.get('CATALOG_DASHBOARD_REFRESH_SECONDS', '60')))

    def updater() -> None:
        while not stop.is_set():
            refresh()
            stop.wait(interval)

    worker = threading.Thread(target=updater, daemon=True)
    worker.start()
    environment = dict(os.environ, **auth, OLIVETIN_LOG_FORMAT='json')
    process = subprocess.Popen(['OliveTin', '-configdir', '/config'], env=environment,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def forward_logs() -> None:
        # Upstream starts at DEBUG before loading logLevel and interpolates auth
        # hashes into its startup debug messages. Never forward those messages.
        assert process.stdout is not None
        for line in process.stdout:
            safe = sanitized_log(line, auth['CATALOG_DASHBOARD_PASSWORD_HASH'])
            if safe is not None:
                print(safe, end='', flush=True)

    threading.Thread(target=forward_logs, daemon=True).start()

    def shutdown(_signum: int, _frame: object) -> None:
        stop.set()
        process.terminate()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    try:
        return process.wait()
    finally:
        stop.set()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('serve', 'refresh', 'healthcheck'):
        commands.add_parser(command)
    action = commands.add_parser('action')
    action.add_argument('verb', choices=['download', 'retry', 'evict'])
    action.add_argument('item_id')
    action.add_argument('--confirm', choices=['0', '1'])
    action.add_argument('--source', choices=['legacy', 'native'], default='legacy')
    args = parser.parse_args()
    try:
        if args.command == 'serve':
            return serve()
        if args.command == 'refresh':
            return 0 if refresh() else 1
        if args.command == 'healthcheck':
            return healthcheck()
        return perform_action(args.verb, args.item_id, args.confirm, args.source)
    except (catalogctl.CatalogError, OSError, ValueError, KeyError) as exc:
        print(f'dashboard: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
