from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('cart_import_sab', Path(__file__).parents[1] / 'scripts/cart_import_sab.py')
sab = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sab)


class CartSabTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.dbpath = self.root / 'history.db'
        self.db = sqlite3.connect(self.dbpath)
        self.addCleanup(self.db.close)
        self.db.executescript('''CREATE TABLE history (nzo_id TEXT,name TEXT,status TEXT,category TEXT,completed INTEGER,storage TEXT,archive INTEGER,time_added INTEGER,url TEXT);
          CREATE TABLE rss(feed TEXT,url TEXT,state TEXT,downloaded_at INTEGER);''')
        self.queue = {'noofslots': 0, 'paused': False, 'slots': []}
        self.processing = 0
        self.source = sab.SabSource(self.root, api=self.api, database=self.dbpath)

    def api(self, mode, **kwargs):
        if mode == 'version':
            return {'version': sab.VERSION}
        if mode == 'queue':
            return {'queue': self.queue}
        if mode == 'history':
            return {'history': {'ppslots': self.processing}}
        raise AssertionError('unexpected API mutation')

    def job(self, identity='new', url='https://indexer.invalid/nzb?apikey=SECRET', **changes):
        row = dict(nzo_id=identity, name='Selected Movie', status='Completed', category='*', completed=200,
                   storage='/data/complete/selected/movie.mkv', archive=None, time_added=100, url=url)
        row.update(changes)
        self.db.execute('INSERT INTO history VALUES (?,?,?,?,?,?,?,?,?)', tuple(row.values()))
        self.db.commit()

    def rss(self, url='https://indexer.invalid/nzb?apikey=SECRET', feed=sab.FEED, state='D', downloaded_at=100):
        self.db.execute('INSERT INTO rss VALUES (?,?,?,?)', (feed, url, state, downloaded_at))
        self.db.commit()

    def test_exact_provenance_preserves_old_and_archived_jobs_for_baseline(self):
        self.job(); self.rss()
        self.job('old', url='old-url', archive=1, status='Failed')
        result = self.source.snapshot()
        self.assertEqual(len(result['history']), 2)
        first, old = result['history']
        self.assertEqual(first['provenance'], {'feed': sab.FEED, 'url_sha256': hashlib.sha256(b'https://indexer.invalid/nzb?apikey=SECRET').hexdigest(), 'downloaded_at': 100, 'unique': True})
        self.assertTrue(old['archive'])
        self.assertIsNone(old['provenance'])
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertNotIn('https://', json.dumps(result))
        self.assertEqual(self.source.job('new'), first)
        self.assertIsNone(self.source.job('missing'))

    def test_default_title_match_is_not_cart_provenance(self):
        self.job(url='unrelated-url'); self.rss()
        self.assertIsNone(self.source.snapshot()['history'][0]['provenance'])

    def test_shared_url_in_another_feed_is_ambiguous(self):
        self.job(); self.rss(); self.rss(feed='Other feed')
        self.assertFalse(self.source.job('new')['provenance']['unique'])

    def test_duplicate_history_url_cannot_borrow_cart_provenance(self):
        self.job(); self.rss()
        self.job('manual', archive=1, status='Failed')
        records = self.source.snapshot()['history']
        self.assertTrue(all(not j['provenance']['unique'] for j in records))

    def test_job_add_time_must_belong_to_the_rss_enqueue_window(self):
        self.rss(downloaded_at=1000)
        for added, expected in [(1001, True), (999, True), (998, False), (1301, False), (None, False)]:
            with self.subTest(added=added):
                self.db.execute('DELETE FROM history'); self.db.commit()
                self.job(time_added=added, completed=2000)
                self.assertEqual(self.source.job('new')['provenance']['unique'], expected)

    def test_held_rss_entry_never_counts_as_acquired(self):
        self.job(); self.rss(state='G', downloaded_at=None)
        self.assertIsNone(self.source.job('new')['provenance'])

    def test_queue_hides_provider_url_info_and_preserves_pauses(self):
        self.queue = {'noofslots': 1, 'noofslots_total': 0, 'paused': False, 'slots': [{'nzo_id': 'pending', 'filename': 'Chosen', 'status': 'Paused', 'url': 'SECRET', 'nzo_info': {'SECRET': 'SECRET'}}]}
        self.processing = 2
        result = self.source.snapshot()
        self.assertEqual(result['queue'][0]['status'], 'Paused')
        self.assertFalse(result['paused'])
        self.assertEqual(result['postprocessing'], 2)
        self.assertNotIn('SECRET', json.dumps(result))

    def test_truncated_queue_refuses_baseline(self):
        self.queue = {'noofslots': 2, 'paused': False, 'slots': [{'nzo_id': 'one'}]}
        with self.assertRaisesRegex(sab.SabError, 'incomplete'):
            self.source.snapshot()

    def test_duplicate_ids_and_malformed_pauses_fail_closed(self):
        for slots, paused in [([{'nzo_id': 'same'}, {'nzo_id': 'same'}], False), ([], 'false')]:
            self.queue = {'noofslots': len(slots), 'paused': paused, 'slots': slots}
            with self.assertRaises(sab.SabError):
                self.source.snapshot()

    def test_database_and_api_failures_never_expose_raw_errors(self):
        with mock.patch.object(self.source, 'api', side_effect=RuntimeError('SECRET-URL')):
            with self.assertRaises(sab.SabError) as error:
                self.source.snapshot()
        self.assertNotIn('SECRET', str(error.exception))
        self.db.execute('DROP TABLE rss'); self.db.commit()
        with self.assertRaises(sab.SabError) as error:
            self.source.snapshot()
        self.assertEqual(str(error.exception), 'sab_snapshot_failed')

    def test_symlink_database_refused_without_modification(self):
        link = self.root / 'link.db'; link.symlink_to(self.dbpath)
        source = sab.SabSource(self.root, api=self.api, database=link)
        with self.assertRaisesRegex(sab.SabError, 'path_invalid'):
            source.snapshot()

    def test_unreviewed_sab_version_refused(self):
        self.source.api = mock.Mock(return_value={'version': 'changed'})
        with self.assertRaisesRegex(sab.SabError, 'version_unreviewed'):
            self.source.snapshot()


if __name__ == '__main__':
    unittest.main()
