#!/usr/bin/env python3
"""Inspect/apply only the approved nonsecret SABnzbd 5.1.3 application defaults.

Run on the cloud host; the API key is read locally and never put in URLs/output.
No server settings, downloads, queue state, histories or services are changed.
Official contracts checked against tag 5.1.3: sabnzbd/cfg.py, config.py, api.py,
and misc.py. See https://github.com/sabnzbd/sabnzbd/tree/5.1.3/sabnzbd .
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

VERSION = '5.1.3'
API_URL = 'http://127.0.0.1:8080/api'
# pp=3 is SAB's normal repair + unpack + archive cleanup. Publication to the
# remote catalog is handled separately by the verified completion publisher.
DESIRED_MISC = {
    'download_dir': '/data/incomplete',
    'complete_dir': '/data/complete',
    'download_free': '30G',
    'complete_free': '30G',
    'fulldisk_autoresume': 1,
    'safe_postproc': 1,
    'enable_unrar': 1,
    'enable_7zip': 1,
    'enable_par_cleanup': 1,
    'direct_unpack': 0,
    'dirscan_dir': '',
    'dirscan_speed': 0,
    'script_dir': '',
    'pre_script': 'None',
    'end_queue_script': 'None',
}
DESIRED_CATEGORY = {'pp': '3', 'script': 'None'}


class SettingsError(RuntimeError):
    """Messages are fixed text or locally controlled allowlisted setting names."""


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SettingsError('SAB API redirect refused; use its cloud loopback endpoint.')


def read_api_key(path: Path) -> str:
    try:
        if path.stat().st_mode & 0o027:
            raise SettingsError('The protected catalog environment must not be group-writable or world-accessible.')
        values = []
        for line in path.read_text(encoding='utf-8').splitlines():
            key, separator, value = line.partition('=')
            if separator and key.strip() == 'SABNZBD_API_KEY':
                values.append(value.strip())
        if len(values) != 1 or not values[0]:
            raise SettingsError('The protected catalog environment must contain one SAB API key.')
        return values[0]
    except OSError:
        raise SettingsError('Cannot read the protected catalog environment.') from None


class SabAPI:
    def __init__(self, key: str):
        self.key = key
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirects())

    def call(self, mode: str, **parameters) -> dict:
        request = urllib.request.Request(
            API_URL,
            data=urllib.parse.urlencode(dict(parameters, mode=mode, output='json', apikey=self.key)).encode(),
            headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST',
        )
        try:
            with self.opener.open(request, timeout=15) as response:
                result = json.load(response)
        except SettingsError:
            raise
        except (OSError, ValueError, urllib.error.HTTPError):
            # Exception text and SAB's error field can contain API keys, URLs,
            # filenames, credentials or raw settings. Never echo them.
            raise SettingsError('SAB loopback API request failed; inspect its private service health.') from None
        if not isinstance(result, dict) or result.get('status') is False or 'error' in result:
            raise SettingsError('SAB rejected the requested operation; no response body was displayed.')
        return result


def misc_value(api: SabAPI, name: str):
    try:
        return api.call('get_config', section='misc', keyword=name)['config']['misc'][name]
    except (KeyError, TypeError):
        raise SettingsError(f'SAB returned no value for approved setting {name}.') from None


def count(value, description: str) -> int:
    try:
        number = int(value)
    except (ValueError, TypeError):
        raise SettingsError(f'SAB returned no reliable {description} count.') from None
    if number < 0:
        raise SettingsError(f'SAB returned a negative {description} count.')
    return number


def job_counts(api: SabAPI) -> tuple[int, int]:
    # limit=1 avoids retrieving the queue/history in bulk. We only retain the
    # aggregate counts, never any job titles, passwords, paths or other fields.
    try:
        queue = api.call('queue', start=0, limit=1)['queue']
        history = api.call('history', start=0, limit=1, archive=0, last_history_update=-1)['history']
        return count(queue['noofslots_total'], 'queued-job'), count(history['ppslots'], 'post-processing-job')
    except (KeyError, TypeError):
        raise SettingsError('SAB job counts were unavailable; no settings may be changed.') from None


def equivalent(value, desired) -> bool:
    # JSON null means a setting is absent, not SAB's literal "None" value
    # that disables scripts. Fresh category creation must set both fields.
    if value is None:
        return False
    if isinstance(desired, int):
        try:
            return int(value) == desired
        except (ValueError, TypeError):
            return False
    return str(value) == desired


def inspect(api: SabAPI) -> dict:
    if api.call('version').get('version') != VERSION:
        raise SettingsError('This helper is reviewed only for SABnzbd 5.1.3; application version differs.')
    current = {name: misc_value(api, name) for name in DESIRED_MISC}
    try:
        category_config = api.call('get_config', section='categories')['config']
        # The wizard can save a server before any category is initialized.
        # get_dconfig returns {} until a category has been created. Inspect
        # must not call get_cats: that nominal read lazily writes defaults.
        categories = [] if category_config == {} else category_config['categories']
        # Untouched installs have no rss section; get_dconfig returns {}.
        feeds = api.call('get_config', section='rss')['config'].get('rss', [])
        defaults = [category for category in categories if category['name'] == '*']
        default_exists = len(defaults) == 1
        if not default_exists and categories:
            raise SettingsError('The default SAB category is missing or ambiguous.')
        default = defaults[0] if default_exists else {'pp': None, 'script': None, 'dir': ''}
        category_current = {name: default[name] for name in DESIRED_CATEGORY}
        # Refuse rather than overwriting unreviewed custom workflows. Only
        # counts are returned; feed URLs/scripts and arbitrary config are hidden.
        overrides = sum(
            category['name'] != '*' and (
                str(category['pp']) not in ('', '-1', '3')
                or str(category['script']).lower() not in ('', 'default', 'none')
                or bool(category['dir'])
            ) for category in categories
        ) + bool(default['dir'])
        enabled_feeds = sum(count(feed['enable'], 'RSS enable flag') != 0 for feed in feeds)
    except (KeyError, TypeError):
        raise SettingsError('SAB category/RSS safeguards could not be inspected.') from None
    queued, postprocessing = job_counts(api)
    return {
        'version': VERSION,
        'queued_jobs': queued, 'postprocessing_jobs': postprocessing,
        'enabled_rss_feeds': enabled_feeds,
        'unreviewed_category_overrides': overrides,
        'settings': current, 'desired_settings': dict(DESIRED_MISC),
        'default_category_exists': default_exists,
        'default_category': category_current, 'desired_default_category': dict(DESIRED_CATEGORY),
        'changes_needed': [name for name, desired in DESIRED_MISC.items() if not equivalent(current[name], desired)]
            + ['default_category.' + name for name, desired in DESIRED_CATEGORY.items() if not equivalent(category_current[name], desired)],
        'safe_to_apply': queued == 0 and postprocessing == 0 and enabled_feeds == 0 and overrides == 0,
    }


def ensure_idle(api: SabAPI) -> None:
    if any(job_counts(api)):
        raise SettingsError('Queue or post-processing contains jobs. No further settings were changed; inspect before retrying.')


def apply(api: SabAPI, before: dict) -> list[str]:
    if not before['safe_to_apply']:
        raise SettingsError('Apply refused: jobs, enabled RSS feeds, or unreviewed category overrides require review.')
    changed = []
    for name, desired in DESIRED_MISC.items():
        if equivalent(before['settings'][name], desired):
            continue
        # Check immediately before every mutation, including complete_dir:
        # unlike download_dir, upstream does not protect that path itself.
        ensure_idle(api)
        api.call('set_config', section='misc', keyword=name, value=desired)
        if not equivalent(misc_value(api, name), desired):
            raise SettingsError(f'SAB did not retain approved setting {name}; inspect before retrying.')
        changed.append(name)
    changed_category = {name: desired for name, desired in DESIRED_CATEGORY.items()
                        if not equivalent(before['default_category'][name], desired)}
    if changed_category:
        ensure_idle(api)
        if not before['default_category_exists']:
            # These are the exact fresh default-category values used by
            # upstream config.get_categories, including NORMAL_PRIORITY=0.
            changed_category.update(priority=0, dir='', order=0)
        api.call('set_config', section='categories', keyword='*', **changed_category)
        changed.extend('default_category.' + name for name in changed_category)
    after = inspect(api)
    if after['changes_needed']:
        raise SettingsError('SAB settings verification did not converge; inspect before retrying.')
    return changed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['inspect', 'apply'], nargs='?', default='inspect')
    parser.add_argument('--env-file', type=Path, default=Path('/srv/usenet/config/catalog.env'))
    args = parser.parse_args(argv)
    try:
        api = SabAPI(read_api_key(args.env_file))
        report = inspect(api)
        if args.operation == 'apply':
            changed = apply(api, report)
            report = inspect(api)
            report['changed'] = changed
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except SettingsError as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 1
    except Exception:
        print(json.dumps({'error': 'Unexpected SAB settings failure; no raw response or exception was displayed.'}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
