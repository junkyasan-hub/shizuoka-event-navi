import datetime as dt
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import publication_gate as gate


class PublicationGateTests(unittest.TestCase):
    def setUp(self):
        self.reviews = json.loads(gate.MANIFEST.read_text())
        self.conn = sqlite3.connect(':memory:')
        self.conn.execute('CREATE TABLE events (id INTEGER PRIMARY KEY,'+','.join(k+' TEXT' for k in gate.FIELDS)+')')
        self.rows = [dict(item['record'], id=i+1) for i,item in enumerate(self.reviews)]
        self.today = dt.date(2026,10,21)

    def tearDown(self):
        self.conn.close()

    def approved(self, rows):
        with patch.object(gate,'reviews',return_value=self.reviews):
            return gate.approved_rows(self.conn, rows, self.today)

    def test_only_exact_reviewed_content_is_published(self):
        self.assertEqual(len(self.approved(self.rows)),len(self.rows))
        changed = dict(self.rows[0],fee='入場無料')
        self.assertEqual(self.approved([changed]),[])
        self.assertEqual(self.approved([dict(self.rows[0],description='架空のSL体験')]),[])
        self.assertEqual(self.approved([dict(self.rows[0],official_url='https://example.com/')]),[])

    def test_imported_and_manual_new_items_are_not_implicitly_approved(self):
        self.assertEqual(self.approved([dict(self.rows[0], title='新規イベント')]),[])
        with patch.object(gate,'reviews',return_value=[]):
            self.assertEqual(gate.approved_rows(self.conn,self.rows,self.today),[])

    def test_expiry_future_dates_and_manual_hides(self):
        self.today = dt.date(2026,10,30)
        self.assertEqual(self.approved(self.rows),[])
        self.today = dt.date(2026,10,18)
        self.assertEqual(self.approved(self.rows),[])
        self.today = dt.date(2026,10,21)
        self.conn.execute('CREATE TABLE event_manual_controls(event_id INTEGER PRIMARY KEY,hidden INTEGER)')
        self.conn.execute('INSERT INTO event_manual_controls VALUES(1,1)')
        self.assertEqual(len(self.approved(self.rows)),len(self.rows)-1)

    def test_public_build_retires_old_detail_urls(self):
        import generate_site as build
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp)/'events.db'
            with sqlite3.connect(db) as conn:
                conn.execute('CREATE TABLE events (id INTEGER PRIMARY KEY,'+','.join(k+' '+('REAL' if k in ('lat','lng') else 'INTEGER' if k.startswith('is_') else 'TEXT') for k in gate.FIELDS)+')')
                for row in [self.rows[0],dict(self.rows[0],id=999,title='裏付けのないイベント')]:
                    conn.execute('INSERT INTO events VALUES('+','.join('?' for _ in range(len(gate.FIELDS)+1))+')',[row['id']]+[row[k] for k in gate.FIELDS])
            out=Path(tmp)/'dist';(out/'events').mkdir(parents=True)
            (out/'events'/'12345.html').write_text('OLD')
            with patch.object(build,'DB_PATH',str(db)),patch.object(build,'OUTPUT_DIR',str(out)),patch.object(build,'EVENTS_OUTPUT_DIR',str(out/'events')),patch.object(gate,'reviews',return_value=self.reviews):
                build.generate_site()
            self.assertNotIn('裏付けのないイベント',(out/'index.html').read_text())
            self.assertIn('掲載情報を確認中',(out/'events'/'999.html').read_text())
            self.assertIn('掲載情報を確認中',(out/'events'/'12345.html').read_text())
            self.assertIn('2026-10-19',(out/'events'/'1.html').read_text())

if __name__ == '__main__':
    unittest.main()
