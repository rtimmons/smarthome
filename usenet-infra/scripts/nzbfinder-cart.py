#!/usr/bin/env python3
"""Safely install the NZBFinder Cart feed in the existing SABnzbd 5.1.3.

The saved NZBFinder key is read only on the cloud host from Prowlarr's protected
database. It is never emitted, put in a command-line argument, or persisted
outside SAB's existing private configuration. New feed entries are first read
with SAB's ``ignore_first`` behavior, so existing cart contents are held rather
than unexpectedly queued. Later user-selected cart additions are downloaded.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ElementTree


VERSION = '5.1.3'
NAME = 'NZBFinder Cart'
SAB_URL = 'http://127.0.0.1:8080/api'
SAB_RSS_TEST_URL = 'http://127.0.0.1:8080/config/rss/test_rss_feed'
ENV_PATH = Path('/srv/usenet/config/catalog.env')
PROWLARR_DATABASE = Path('/srv/usenet/config/prowlarr/prowlarr.db')
MAX_RESPONSE = 4 * 1024 * 1024
EXPECTED = {'cat': 'Default', 'pp': '3', 'script': 'None', 'priority': 0, 'enable': True}


class CartError(RuntimeError):
    """Only nonsecret, fixed diagnostic categories cross this boundary."""


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, new_url):
        return None


def protected_regular(path: Path) -> None:
    try:
        info = path.lstat()
    except OSError:
        raise CartError('protected_configuration_unavailable') from None
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o027:
        raise CartError('protected_configuration_permissions_invalid')


def env_value(name: str, path: Path = ENV_PATH) -> str:
    protected_regular(path)
    try:
        values = [value.strip().strip('\"\'') for line in path.read_text().splitlines()
                  for key, separator, value in [line.partition('=')]
                  if separator and key.strip() == name]
    except OSError:
        raise CartError('protected_configuration_unavailable') from None
    if len(values) != 1 or not values[0]:
        raise CartError('protected_configuration_value_unavailable')
    return values[0]


def nzbfinder_key(database: Path = PROWLARR_DATABASE) -> str:
    protected_regular(database)
    try:
        with closing(sqlite3.connect(database.absolute().as_uri() + '?mode=ro', uri=True, timeout=15)) as connection:
            rows = connection.execute('SELECT Settings, Enable FROM Indexers WHERE Name = ?', ('NZBFinder',)).fetchall()
    except sqlite3.Error:
        raise CartError('nzbfinder_saved_indexer_unavailable') from None
    if len(rows) != 1 or rows[0][1] not in (1, True):
        raise CartError('nzbfinder_saved_indexer_unavailable')
    try:
        settings = json.loads(rows[0][0])
        key = settings['apiKey']
    except (KeyError, TypeError, ValueError):
        raise CartError('nzbfinder_saved_indexer_invalid') from None
    if (not isinstance(key, str) or len(key) != 32 or any(character not in '0123456789abcdef' for character in key)):
        raise CartError('nzbfinder_saved_key_invalid')
    if settings.get('baseUrl', '').rstrip('/') != 'https://nzbfinder.ws' or settings.get('apiPath') != '/api':
        raise CartError('nzbfinder_endpoint_requires_review')
    return key


def feed_url(key: str, *, download: bool = True) -> str:
    return 'https://nzbfinder.ws/rss/cart?' + urllib.parse.urlencode({
        'api_token': key, 'dl': '1' if download else '0', 'del': '0',
    })


class SabAPI:
    def __init__(self, key: str):
        self.key = key
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirects())

    def call(self, mode: str, **parameters):
        request = urllib.request.Request(SAB_URL,
            data=urllib.parse.urlencode({'mode': mode, 'output': 'json', 'apikey': self.key, **parameters}).encode(),
            headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
        try:
            with self.opener.open(request, timeout=30) as response:
                result = json.loads(response.read(MAX_RESPONSE + 1))
        except Exception:
            raise CartError('sab_request_failed') from None
        if not isinstance(result, dict) or result.get('status') is False or 'error' in result:
            raise CartError('sab_request_rejected')
        return result

    def test_feed_without_download(self) -> None:
        request = urllib.request.Request(SAB_RSS_TEST_URL,
            data=urllib.parse.urlencode({'apikey': self.key, 'feed': NAME}).encode(),
            headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
        try:
            self.opener.open(request, timeout=60)
        except urllib.error.HTTPError as error:
            if error.code not in (301, 302, 303):
                raise CartError('sab_rss_test_failed') from None
        except Exception:
            raise CartError('sab_rss_test_failed') from None


def external_probe(url: str) -> None:
    request = urllib.request.Request(url, headers={'User-Agent': 'SABnzbd/' + VERSION})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirects())
    try:
        with opener.open(request, timeout=30) as response:
            body = response.read(MAX_RESPONSE + 1)
        if len(body) > MAX_RESPONSE or ElementTree.fromstring(body).tag.rsplit('}', 1)[-1] != 'rss':
            raise ValueError()
    except Exception:
        raise CartError('nzbfinder_cart_feed_validation_failed') from None


def feeds(api: SabAPI) -> list[dict]:
    try:
        result = api.call('get_config', section='rss')['config'].get('rss', [])
    except (KeyError, TypeError):
        raise CartError('sab_rss_configuration_unavailable') from None
    if not isinstance(result, list) or any(not isinstance(feed, dict) for feed in result):
        raise CartError('sab_rss_configuration_unavailable')
    return result


def matches(feed: dict, key: str, *, enabled: bool = True) -> bool:
    try:
        uri = feed['uri']
        parsed = urllib.parse.urlsplit(uri[0])
        query = urllib.parse.parse_qs(parsed.query, strict_parsing=True)
        filters = feed['filter0']
        return (isinstance(uri, list) and len(uri) == 1 and parsed.scheme == 'https' and parsed.hostname == 'nzbfinder.ws'
                and parsed.path == '/rss/cart' and not parsed.username and not parsed.password and not parsed.fragment
                and query == {'api_token': [key], 'dl': ['1'], 'del': ['0']}
                and str(feed['cat']) == EXPECTED['cat'] and str(feed['pp']) == EXPECTED['pp']
                and str(feed['script']) == EXPECTED['script'] and int(feed['priority']) == EXPECTED['priority']
                and bool(feed['enable']) is enabled
                # -100 is SAB's "use the feed priority" sentinel. The feed
                # itself is explicitly normal priority (0).
                and list(filters) == ['', '', '', 'A', '*', -100, '1'])
    except (KeyError, TypeError, ValueError):
        return False


def public_report(api: SabAPI, key: str, *, changed: bool = False, first_scan_held: bool = False) -> dict:
    current = feeds(api)
    configured = [feed for feed in current if feed.get('name') == NAME]
    if len(configured) > 1:
        raise CartError('duplicate_nzbfinder_cart_feeds')
    if configured and not matches(configured[0], key, enabled=bool(configured[0].get('enable'))):
        raise CartError('nzbfinder_cart_requires_review')
    try:
        interval = int(api.call('get_config', section='misc', keyword='rss_rate')['config']['misc']['rss_rate'])
    except (KeyError, TypeError, ValueError):
        raise CartError('sab_rss_interval_unavailable') from None
    return {'feed': NAME, 'configured': len(configured) == 1, 'enabled': bool(configured and configured[0].get('enable')),
            'poll_minutes': interval, 'changed': changed, 'first_scan_held': first_scan_held}


def configure(api: SabAPI, key: str) -> dict:
    if api.call('version').get('version') != VERSION:
        raise CartError('sab_version_unreviewed')
    before = public_report(api, key)
    if before['configured']:
        if not before['enabled']:
            api.test_feed_without_download()
            api.call('set_config', section='rss', keyword=NAME, enable=1)
        if before['poll_minutes'] != 15:
            api.call('set_config', section='misc', keyword='rss_rate', value=15)
        return public_report(api, key, changed=not before['enabled'] or before['poll_minutes'] != 15,
                             first_scan_held=not before['enabled'])
    external_probe(feed_url(key))
    # Create disabled, then use SAB's native test action with ignore_first=True.
    # This only records current cart entries as held; it never queues an NZB.
    api.call('set_config', section='rss', name=NAME, uri=feed_url(key), cat='Default', pp='3',
             script='None', priority=0, enable=0)
    staged = feeds(api)
    created = [feed for feed in staged if feed.get('name') == NAME]
    if len(created) != 1 or not matches(created[0], key, enabled=False):
        raise CartError('nzbfinder_cart_creation_readback_failed')
    api.test_feed_without_download()
    api.call('set_config', section='rss', keyword=NAME, enable=1)
    if public_report(api, key)['poll_minutes'] != 15:
        api.call('set_config', section='misc', keyword='rss_rate', value=15)
    return public_report(api, key, changed=True, first_scan_held=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('inspect', 'configure'), nargs='?', default='inspect')
    args = parser.parse_args(argv)
    try:
        key = nzbfinder_key()
        api = SabAPI(env_value('SABNZBD_API_KEY'))
        report = configure(api, key) if args.command == 'configure' else public_report(api, key)
        print(json.dumps(report, sort_keys=True))
        return 0
    except CartError as error:
        print(json.dumps({'error': str(error)}, sort_keys=True))
        return 1
    except Exception:
        print(json.dumps({'error': 'unexpected_nzbfinder_cart_failure'}, sort_keys=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
