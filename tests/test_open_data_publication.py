import csv
import datetime as dt
import io
import sqlite3
import unittest
from unittest.mock import patch
from collect_open_data import REQUIRED,sync
from publication_gate import FIELDS,approved_rows

NOW=dt.datetime(2026,10,21,tzinfo=dt.timezone.utc)

def csv_data(**changes):
    row={key:'' for key in REQUIRED}
    row.update({'NO':'20261021001','イベント名':'市の展示会','開始日':'2026-10-24','終了日':'2026-10-25','カテゴリー':'イベント','場所名称':'市民会館','料金(基本)':'無料'})
    row.update(changes)
    stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=sorted(REQUIRED));writer.writeheader();writer.writerow(row)
    return stream.getvalue().encode('cp932')

class OpenDataPublicationTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:')
        self.conn.execute('CREATE TABLE events(id INTEGER PRIMARY KEY,'+','.join(k+' '+('INTEGER' if k.startswith('is_') else 'REAL' if k in ('lat','lng') else 'TEXT') for k in FIELDS)+')')
    def tearDown(self):self.conn.close()
    def visible(self,day=dt.date(2026,10,21)):
        with patch('publication_gate.reviews',return_value=[]):
            return approved_rows(self.conn,self.conn.execute('SELECT * FROM events').fetchall(),day)
    def test_valid_feed_publishes_without_manual_manifest_and_is_idempotent(self):
        self.assertEqual(sync(self.conn,csv_data(),NOW)['saved'],1)
        self.assertEqual(len(self.visible()),1)
        sync(self.conn,csv_data(),NOW)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM events').fetchone()[0],1)
        sync(self.conn,csv_data(**{'料金(基本)':'500円'}),NOW)
        self.assertEqual(self.visible()[0]['fee'],'500円')
    def test_post_import_edit_requires_review(self):
        sync(self.conn,csv_data(),NOW)
        self.conn.execute("UPDATE events SET summary='架空の特典'")
        self.assertEqual(self.visible(),[])
    def test_invalid_feed_does_not_change_data_or_approval(self):
        sync(self.conn,csv_data(),NOW)
        for data in [b'bad',csv_data(**{'開始日':'2026-99-99'}),csv_data(**{'場所名称':''}),csv_data(**{'イベント名':'開催中止'})]:
            with self.assertRaises(ValueError):sync(self.conn,data,NOW)
            self.assertEqual(len(self.visible()),1)
    def test_old_evidence_expires(self):
        sync(self.conn,csv_data(),NOW)
        self.assertEqual(self.visible(dt.date(2026,10,29)),[])
    def test_removed_source_rows_lose_approval(self):
        sync(self.conn,csv_data(),NOW)
        sync(self.conn,csv_data(**{'NO':'new','イベント名':'別の展示会'}),NOW)
        self.assertEqual(len(self.visible()),1)
        self.assertEqual(self.visible()[0]['title'],'別の展示会')
    def test_manual_hidden_identity_is_not_recreated(self):
        sync(self.conn,csv_data(),NOW)
        self.conn.execute('CREATE TABLE event_manual_controls(event_id INTEGER,hidden INTEGER)')
        self.conn.execute('INSERT INTO event_manual_controls VALUES(1,1)')
        self.assertEqual(sync(self.conn,csv_data(),NOW)['saved'],0)
        self.assertEqual(self.visible(),[])

if __name__=='__main__':unittest.main()
