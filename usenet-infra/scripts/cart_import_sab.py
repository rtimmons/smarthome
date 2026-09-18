"""Read bounded SAB queue/history and exact cart provenance without returning URLs.

SAB 5.1.3 persists a job's originating URL in history and the native RSS table.
Default category or a matching title alone never establishes cart provenance.
"""
from __future__ import annotations

from contextlib import closing
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import stat
import urllib.parse
import urllib.request

FEED = 'NZBGeek Cart'
FEEDS = frozenset((FEED, 'NZBFinder Cart'))
VERSION = '5.1.3'
LIMIT = 100_000
PAGE = 1000
# Native RSS timestamps the enqueue; URL fetching may construct the final NZO
# slightly later. This is a conservative admission bound, not a SAB guarantee:
# delayed/retried fetches remain held rather than borrowing old RSS provenance.
MAX_RSS_JOB_DELAY = 300


class SabError(RuntimeError):
    """Only fixed error categories may cross this adapter boundary."""


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise SabError('sab_redirect_refused')


def count(value):
    if isinstance(value, bool) or not str(value).isdigit():
        raise SabError('sab_count_invalid')
    number = int(value)
    if number > LIMIT:
        raise SabError('sab_count_exceeds_bound')
    return number


def epoch(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise SabError('sab_timestamp_invalid')
    return value


class SabSource:
    def __init__(self, root=Path('/srv/usenet'), *, api=None, database=None):
        self.root = Path(root)
        self.database = Path(database) if database is not None else self.root / 'config/sabnzbd/admin/history1.db'
        self.api = api or self._call
        self._key = None

    def _call(self, mode, **parameters):
        try:
            if self._key is None:
                path = self.root / 'config/catalog.env'
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o027:
                    raise SabError('sab_key_permissions_invalid')
                values = [line.partition('=')[2].strip() for line in path.read_text().splitlines()
                          if line.partition('=')[0] == 'SABNZBD_API_KEY']
                if len(values) != 1 or not values[0]:
                    raise SabError('sab_key_missing')
                self._key = values[0]
            body = urllib.parse.urlencode({'mode': mode, 'output': 'json', 'apikey': self._key, **parameters}).encode()
            request = urllib.request.Request('http://127.0.0.1:8080/api', data=body)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirects())
            with opener.open(request, timeout=30) as response:
                raw = response.read(16 * 1024 * 1024 + 1)
            if len(raw) > 16 * 1024 * 1024:
                raise SabError('sab_response_exceeds_bound')
            return json.loads(raw)
        except SabError:
            raise
        except Exception:
            raise SabError('sab_request_failed') from None

    def _queue(self):
        jobs, seen, expected, paused = [], set(), None, None
        for start in range(0, LIMIT, PAGE):
            page = self.api('queue', start=start, limit=PAGE)['queue']
            # SAB's noofslots_total excludes individually paused jobs. With no
            # filters, noofslots includes all matching jobs across every page.
            total = count(page['noofslots'])
            if type(page.get('paused')) is not bool:
                raise SabError('sab_pause_state_invalid')
            if expected is None:
                expected, paused = total, page['paused']
            if total != expected or page['paused'] != paused:
                raise SabError('sab_queue_changed_during_read')
            slots = page['slots']
            if not isinstance(slots, list) or len(slots) > PAGE:
                raise SabError('sab_queue_page_invalid')
            for job in slots:
                identity = job['nzo_id']
                if not isinstance(identity, str) or not identity or identity in seen:
                    raise SabError('sab_queue_identity_invalid')
                seen.add(identity)
                # Deliberately exclude URLs, nzo_info, provider failures and credentials.
                jobs.append({key: job[key] for key in
                             ('nzo_id', 'filename', 'status', 'priority', 'cat', 'mb', 'mbleft', 'percentage', 'time_added')
                             if key in job})
            if len(jobs) == expected:
                return jobs, paused
            if len(slots) < PAGE or len(jobs) > expected:
                raise SabError('sab_queue_incomplete')
        raise SabError('sab_queue_exceeds_bound')

    def snapshot(self):
        try:
            if self.api('version').get('version') != VERSION:
                raise SabError('sab_version_unreviewed')
            queue, paused = self._queue()
            processing = count(self.api('history', start=0, limit=1, archive=0, last_history_update=-1)['history']['ppslots'])
            # SQLite read-only mode never creates or modifies SAB's database.
            path = self.database.absolute()
            if not stat.S_ISREG(path.lstat().st_mode) or any(p.is_symlink() for p in path.parents):
                raise SabError('sab_database_path_invalid')
            with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=10)) as db:
                db.row_factory = sqlite3.Row
                db.execute('BEGIN')
                rss = list(db.execute('SELECT feed,url,state,downloaded_at,title,priority,size,initial_scan FROM rss LIMIT ?', (LIMIT + 1,)))
                history = list(db.execute('SELECT nzo_id,name,status,category,completed,path,storage,archive,time_added,url FROM history LIMIT ?', (LIMIT + 1,)))
            if len(rss) > LIMIT or len(history) > LIMIT:
                raise SabError('sab_database_exceeds_bound')
            by_url, by_title = {}, {}
            for row in rss:
                if row['url']:
                    by_url.setdefault(row['url'], []).append(row)
                by_title.setdefault(row['title'], []).append(row)
            history_by_url = {}
            for row in history:
                if row['url']:
                    history_by_url.setdefault(row['url'], []).append(row)
            # SAB materializes priority=-2 as status=Paused, priority=Normal.
            # Match the full release, bounded enqueue time and advertised bytes
            # to one saved paused cart arrival; a title alone is never sufficient.
            queue_titles = Counter(job.get('filename') for job in queue)
            for job in queue:
                matches = by_title.get(job.get('filename'), [])
                if len(matches) != 1 or queue_titles[job.get('filename')] != 1:
                    continue
                row = matches[0]
                if (job.get('status') != 'Paused' or row['feed'] not in FEEDS
                        or row['state'] != 'D' or row['priority'] != -2 or row['initial_scan']
                        or not row['url'] or len(by_url.get(row['url'], [])) != 1
                        or history_by_url.get(row['url'])):
                    continue
                try:
                    added, downloaded = epoch(job.get('time_added')), epoch(row['downloaded_at'])
                    size, expected = float(job.get('mb', 0)) * 1024 ** 2, float(row['size'])
                    left = float(job.get('mbleft', 0)) * 1024 ** 2
                    if (min(added, downloaded, size, expected) <= 0
                            or not all(math.isfinite(v) for v in (size, expected, left))
                            or not -1 <= added - downloaded <= MAX_RSS_JOB_DELAY
                            or abs(size - expected) > 64 * 1024 or abs(size - left) > 64 * 1024
                            or float(job.get('percentage', -1)) != 0):
                        continue
                except (SabError, TypeError, ValueError, OverflowError):
                    continue
                job['paused_intake'] = {'feed': row['feed'], 'downloaded_at': downloaded,
                                        'url_sha256': hashlib.sha256(row['url'].encode()).hexdigest()}
            records, seen = [], set()
            for row in history:
                identity = row['nzo_id']
                if not isinstance(identity, str) or not identity or identity in seen:
                    raise SabError('sab_history_identity_invalid')
                seen.add(identity)
                item = {key: row[key] for key in ('nzo_id', 'name', 'status', 'category', 'path', 'storage')}
                item.update(completed=epoch(row['completed']), time_added=epoch(row['time_added'] or 0),
                            archive=bool(row['archive']), provenance=None)
                item['source_url_sha256'] = hashlib.sha256(row['url'].encode()).hexdigest() if row['url'] else None
                matches = by_url.get(row['url'], []) if row['url'] else []
                cart = [r for r in matches if r['feed'] in FEEDS and r['state'] == 'D' and r['downloaded_at'] is not None]
                if len(cart) == 1:
                    downloaded_at = epoch(cart[0]['downloaded_at'])
                    added = item['time_added']
                    # Manual per-item RSS calls flag the entry immediately after
                    # enqueue, so allow one second of integer-clock rounding.
                    bound = (downloaded_at > 0 and added > 0 and item['completed'] >= max(added, downloaded_at)
                             and -1 <= added - downloaded_at <= MAX_RSS_JOB_DELAY)
                    item['provenance'] = {'feed': cart[0]['feed'], 'url_sha256': hashlib.sha256(row['url'].encode()).hexdigest(),
                                          'downloaded_at': downloaded_at,
                                          'unique': len(matches) == 1 and len(history_by_url[row['url']]) == 1 and bound}
                records.append(item)
            hashes = sorted({hashlib.sha256(row['url'].encode()).hexdigest() for row in rss if row['url']})
            return {'queue': queue, 'history': records, 'rss_hashes': hashes,
                    'paused': paused, 'postprocessing': processing}
        except SabError:
            raise
        except Exception:
            raise SabError('sab_snapshot_failed') from None

    def job(self, job_id):
        return next((j for j in self.snapshot()['history'] if j['nzo_id'] == job_id), None)
