#!/usr/bin/env python3
"""Submit once and inspect only SABnzbd's official 100 MB diagnostic fixture.

Standalone cloud-host helper, suitable for execution through Python's stdin.
An fsynced intent precedes submission; uncertain requests never auto-reenqueue.
No provider secret, API key, arbitrary queue entry, or upstream message is output.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time
import urllib.parse
import urllib.request


API_URL = 'http://127.0.0.1:8080/api'
ENV_PATH = Path('/srv/usenet/config/catalog.env')
RECEIPT_PATH = Path('/srv/usenet/state/sab-smoke-test.json')
FIXTURE_URL = 'https://sabnzbd.org/tests/test_download_100MB.nzb'
FIXTURE_NAME = 'authorized-sab-smoke-100mb'
JOB_ID = re.compile(r'[A-Za-z0-9_-]{1,128}')
SERVER_SETTINGS = dict(required=1, optional=0, priority=0, connections=20,
                       ssl_verify=3, ssl=1, port=563, enable=1, retention=0)
MISC_SETTINGS = {
    'download_dir': '/data/incomplete', 'complete_dir': '/data/complete',
    'download_free': '30G', 'complete_free': '30G', 'fulldisk_autoresume': 0,
    'safe_postproc': 1, 'enable_unrar': 1, 'enable_7zip': 1, 'enable_par_cleanup': 1,
    'direct_unpack': 0, 'dirscan_dir': '', 'dirscan_speed': 0, 'script_dir': '',
    'pre_script': 'None', 'end_queue_script': 'None',
}
STATES = {'Downloading', 'Queued', 'Paused', 'Fetching', 'Checking', 'Repairing',
          'Extracting', 'Moving', 'Running', 'Verifying', 'Completed', 'Failed',
          'QuickCheck', 'Waiting', 'Deleting', 'Grabbing', 'Propagating'}


class SmokeError(Exception):
    """Fixed safe diagnostic categories only."""


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_api_key(path: Path = ENV_PATH) -> str:
    try:
        if path.stat().st_mode & 0o027:
            raise SmokeError('catalog_environment_permissions_invalid')
        values = [value.strip().strip('\"\'') for line in path.read_text().splitlines()
                  for key, separator, value in [line.partition('=')]
                  if separator and key.strip() == 'SABNZBD_API_KEY']
        if len(values) != 1 or not values[0]:
            raise SmokeError('api_key_unavailable')
        return values[0]
    except OSError:
        raise SmokeError('api_key_unavailable') from None


class SabAPI:
    def __init__(self, key: str):
        self.key = key
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirects())

    def call(self, mode: str, **parameters) -> dict:
        request = urllib.request.Request(
            API_URL, method='POST', headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data=urllib.parse.urlencode(dict(parameters, mode=mode, output='json', apikey=self.key)).encode(),
        )
        try:
            with self.opener.open(request, timeout=45) as response:
                payload = json.load(response)
            if not isinstance(payload, dict):
                raise SmokeError('unexpected_api_response')
            return payload
        except SmokeError:
            raise
        except Exception:
            raise SmokeError('api_request_failed') from None


def number(value) -> float:
    try:
        result = float(value)
        if not math.isfinite(result) or result < 0:
            raise ValueError()
        return result
    except (TypeError, ValueError, OverflowError):
        raise SmokeError('unexpected_numeric_response') from None


def equivalent(value, expected) -> bool:
    if isinstance(expected, int):
        return number(value) == expected
    return value == expected


def ensure_idle(api: SabAPI) -> None:
    queue = api.call('queue', start=0, limit=1)['queue']
    history = api.call('history', start=0, limit=1, archive=0, last_history_update=-1)['history']
    if number(queue['noofslots_total']) or number(history['ppslots']):
        raise SmokeError('queue_or_postprocessing_not_empty')
    if queue.get('paused') not in (False, 0, '0'):
        raise SmokeError('queue_paused_or_pause_state_unknown')


def preflight(api: SabAPI) -> None:
    if api.call('version').get('version') != '5.1.3':
        raise SmokeError('unsupported_sab_version')
    servers = api.call('get_config', section='servers')['config']['servers']
    enabled = [server for server in servers if number(server['enable']) != 0]
    if len(enabled) != 1 or enabled[0].get('host') != 'news.eweka.nl':
        raise SmokeError('sole_enabled_eweka_server_required')
    server = enabled[0]
    if any(not equivalent(server.get(key), value) for key, value in SERVER_SETTINGS.items()):
        raise SmokeError('secure_eweka_settings_required')
    if not server.get('username') or not server.get('password'):
        raise SmokeError('saved_provider_credentials_missing')
    for key, expected in MISC_SETTINGS.items():
        value = api.call('get_config', section='misc', keyword=key)['config']['misc'][key]
        if not equivalent(value, expected):
            raise SmokeError('approved_storage_and_processing_settings_required')
    categories = api.call('get_config', section='categories')['config']['categories']
    defaults = [category for category in categories if category.get('name') == '*']
    if len(defaults) != 1 or str(defaults[0].get('pp')) != '3' or defaults[0].get('script') != 'None' or defaults[0].get('dir') != '':
        raise SmokeError('safe_default_category_required')
    rss = api.call('get_config', section='rss')['config'].get('rss', [])
    if any(number(feed['enable']) for feed in rss):
        raise SmokeError('enabled_rss_feed_requires_review')
    ensure_idle(api)


def write_receipt(path: Path, payload: dict) -> None:
    fd, temporary = tempfile.mkstemp(prefix='.sab-smoke-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(payload, stream, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def read_receipt(path: Path) -> dict:
    try:
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077:
            raise SmokeError('receipt_permissions_invalid')
        payload = json.loads(path.read_text())
        allowed = {'schema_version', 'fixture_url', 'fixture_name', 'state', 'created_at', 'job_id'}
        if (not isinstance(payload, dict) or set(payload) != allowed or payload['schema_version'] != 1
                or payload['fixture_url'] != FIXTURE_URL or payload['fixture_name'] != FIXTURE_NAME
                or payload['state'] not in {'intent', 'submitted', 'ambiguous', 'rejected'}):
            raise SmokeError('receipt_invalid_manual_review_required')
        number(payload['created_at'])
        job = payload['job_id']
        if job is not None and (not isinstance(job, str) or not JOB_ID.fullmatch(job)):
            raise SmokeError('receipt_invalid_manual_review_required')
        if (payload['state'] == 'submitted') != (job is not None):
            raise SmokeError('receipt_invalid_manual_review_required')
        return payload
    except SmokeError:
        raise
    except Exception:
        raise SmokeError('receipt_invalid_manual_review_required') from None


@contextmanager
def receipt_lock(path: Path):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path.with_suffix('.lock'), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SmokeError('smoke_test_operation_already_running') from None
        yield


def start(api: SabAPI, path: Path = RECEIPT_PATH) -> dict:
    with receipt_lock(path):
        if path.exists() or path.is_symlink():
            previous = read_receipt(path)
            if previous['state'] != 'submitted':
                raise SmokeError('prior_submission_uncertain_manual_review_required')
            return {'status': 'already_submitted', 'reenqueued': False}
        preflight(api)
        receipt = dict(schema_version=1, fixture_url=FIXTURE_URL, fixture_name=FIXTURE_NAME,
                       state='intent', created_at=time.time(), job_id=None)
        # This durable intent survives process death or an uncertain HTTP reply.
        write_receipt(path, receipt)
        try:
            response = api.call('addurl', name=FIXTURE_URL, priority=0, pp=3,
                                cat='*', script='None', nzbname=FIXTURE_NAME)
            ids = response.get('nzo_ids')
            if response.get('status') is False:
                receipt['state'] = 'rejected'
                write_receipt(path, receipt)
                raise SmokeError('submission_rejected_manual_review_required')
            if (response.get('status') is not True or not isinstance(ids, list) or len(ids) != 1
                    or not isinstance(ids[0], str) or not JOB_ID.fullmatch(ids[0])):
                raise SmokeError('submission_response_ambiguous')
            receipt.update(state='submitted', job_id=ids[0])
            write_receipt(path, receipt)
        except BaseException:
            if receipt['state'] == 'intent':
                receipt['state'] = 'ambiguous'
                write_receipt(path, receipt)
            raise
        return {'status': 'submitted', 'expected_size_mb': 100, 'repair_unpack_policy': 'repair_unpack_cleanup'}


def status(api: SabAPI, path: Path = RECEIPT_PATH) -> dict:
    with receipt_lock(path):
        if not path.exists() and not path.is_symlink():
            return {'status': 'not_started'}
        receipt = read_receipt(path)
        if receipt['state'] != 'submitted':
            raise SmokeError('prior_submission_uncertain_manual_review_required')
        job_id = receipt['job_id']
        # Exact-ID filters are supported for URL placeholders, active downloads,
        # active post-processing and history. Never search by title or enumerate.
        queue = api.call('queue', nzo_ids=job_id, start=0, limit=1)['queue']['slots']
        history = api.call('history', nzo_ids=job_id, start=0, limit=1, archive=0,
                           last_history_update=-1)['history']['slots']
        queue = [entry for entry in queue if entry.get('nzo_id') == job_id]
        history = [entry for entry in history if entry.get('nzo_id') == job_id]
        if len(queue) > 1 or len(history) > 1:
            raise SmokeError('duplicate_job_id_response')
        if not queue and not history:
            return {'status': 'job_not_found', 'reenqueued': False}
        item = history[0] if history else queue[0]
        state = item.get('status')
        result = {'status': state.lower() if state in STATES else 'unknown'}
        if history:
            stages = item.get('stage_log', [])
            names = {entry.get('name') for entry in stages if isinstance(entry, dict)}
            repair_actions = [action for entry in stages if isinstance(entry, dict) and entry.get('name') == 'Repair'
                              for action in entry.get('actions', []) if isinstance(action, str)]
            unpack_actions = [action for entry in stages if isinstance(entry, dict) and entry.get('name') == 'Unpack'
                              for action in entry.get('actions', []) if isinstance(action, str)]
            repair_success = any(re.search(r'Quick Check OK|all files correct|Repaired in ', action) for action in repair_actions)
            unpack_success = any(re.search(r'Unpacked \d+ files/folders in ', action) for action in unpack_actions)
            result.update(
                size_bytes=int(number(item.get('bytes', 0))),
                downloaded_bytes=int(number(item.get('downloaded', 0))),
                download_seconds=number(item.get('download_time', 0)),
                postprocess_seconds=number(item.get('postproc_time', 0)),
                repair_unpack_policy_confirmed=item.get('pp') == 'D',
                verification_stage_observed='Repair' in names,
                unpack_stage_observed='Unpack' in names,
                verification_success_reported=repair_success,
                unpack_success_reported=unpack_success,
                failure_reported=bool(item.get('fail_message')),
                processing_checks_passed=bool(state == 'Completed' and item.get('pp') == 'D'
                                              and not item.get('fail_message') and repair_success and unpack_success),
            )
            # Stage presence is an indicator, not a fabricated repair verdict.
            if state == 'Completed' and item.get('storage') == '/data/complete/' + FIXTURE_NAME:
                result['test_directory'] = '/srv/usenet/downloads/complete/' + FIXTURE_NAME
        else:
            for source, target in [('mb', 'size_mb'), ('mbleft', 'remaining_mb'), ('percentage', 'percent')]:
                if source in item:
                    result[target] = number(item[source])
        return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('start', 'status'))
    args = parser.parse_args(argv)
    try:
        api = SabAPI(read_api_key())
        result = start(api) if args.command == 'start' else status(api)
        print(json.dumps(result, sort_keys=True))
        return 1 if result['status'] == 'failed' else 0
    except SmokeError as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, sort_keys=True))
        return 1
    except Exception:
        print(json.dumps({'status': 'error', 'error': 'unexpected_response_manual_review_required'}, sort_keys=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
