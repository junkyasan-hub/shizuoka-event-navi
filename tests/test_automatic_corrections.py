from db_fixture import create_test_db
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import ai_rewriter
import collect_events
from automatic_corrections import plan_corrections
from event_sources import SOURCES, factual_event
from event_verification import recheck_published
from manual_events import apply, fingerprint

class CorrectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.db=Path(self.temp.name)/'events.db'
        create_test_db(self.db)
        self.original=factual_event(SOURCES[1],'https://www.visit-shizuoka.com/event/detail_999997.html','自動訂正テスト','2099年10月18日','旧会場')
        with sqlite3.connect(self.db) as c:
            collect_events.save_events(c,[(self.original,None)],[{'summary':'2099年10月18日開催','description':'旧会場で開催。'}])
            self.id=c.execute('SELECT MAX(id) FROM events').fetchone()[0]
        self.actual=copy.deepcopy(self.original)
        self.actual.update(date_str='2099年10月19日',source_date_str='2099年10月19日',start_date='2099-10-19',end_date='2099-10-19',location='新会場')
    def tearDown(self):self.temp.cleanup()
    def plan(self, actual=None, observed=True):
        event=actual or self.actual
        with sqlite3.connect(self.db) as c:
            checks=recheck_published(c,[event],{SOURCES[1].name},None,0)
            return plan_corrections(c,checks,[event] if observed else [])
    def test_valid_official_detail_and_same_year(self):
        corrections,holds=self.plan()
        self.assertEqual(len(corrections),1)
        self.assertEqual(corrections[0][1],self.id)
        self.assertEqual(corrections[0][0]['location'],'新会場')
        self.assertFalse(holds)
    def test_manual_protection(self):
        with sqlite3.connect(self.db) as c:
            c.row_factory=sqlite3.Row
            row=c.execute('SELECT * FROM events WHERE id=?',(self.id,)).fetchone()
            apply(c,dict(action='hide',id=self.id,version=fingerprint(row),fields={}))
        corrections,holds=self.plan()
        self.assertFalse(corrections)
        self.assertTrue(any('保護' in h['reason'] for h in holds))
    def test_other_year_name_root_url_and_uncertain_dates_hold(self):
        cases=[dict(date_str='2100年10月19日',source_date_str='2100年10月19日',start_date='2100-10-19',end_date='2100-10-19'),
               dict(title='別イベント'),dict(source_url='https://www.visit-shizuoka.com/'),dict(start_date=None,end_date=None)]
        for changes in cases:
            actual={**self.actual,**changes}
            corrections,_=self.plan(actual)
            self.assertEqual(corrections,[],changes)
    def test_duplicate_titles_and_foreign_domain_hold(self):
        with sqlite3.connect(self.db) as c:
            copy_event={**self.original,'source_url':self.original['source_url']+'-other'}
            collect_events.save_events(c,[(copy_event,None)],[{'summary':'案内','description':'説明'}])
        self.assertEqual(self.plan()[0],[])
        actual={**self.actual,'source_url':'https://example.org/event/detail_999997.html'}
        self.assertEqual(self.plan(actual)[0],[])
    def test_details_obtained_in_recheck_keep_definite_dates(self):
        corrections,_=self.plan(observed=False)
        self.assertEqual(len(corrections),1)
        self.assertEqual(corrections[0][0]['start_date'],'2099-10-19')
    def test_repeat_run_no_duplicate_history_and_body_is_refreshed(self):
        args=['--db',str(self.db),'--max-rechecks','0','--no-rewrite','--output',str(Path(self.temp.name)/'report.json')]
        with patch.object(collect_events,'collect',side_effect=lambda source,*args:[self.actual] if source.city=='静岡市' else []):
            self.assertEqual(collect_events.main(args),0)
            self.assertEqual(collect_events.main(args),0)
        with sqlite3.connect(self.db) as c:
            date,body=c.execute('SELECT date_str,description FROM events WHERE id=?',(self.id,)).fetchone()
            self.assertEqual(date,'2099年10月19日')
            self.assertNotIn('旧会場',body)
            self.assertIn('新会場',body)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM event_auto_correction_history').fetchone()[0],1)
        report=json.loads((Path(self.temp.name)/'report.json').read_text())
        self.assertEqual(report['saved'],0)
    def test_failed_body_keeps_old_record_and_has_no_correction_history(self):
        before= self.db.read_bytes()
        with patch.object(collect_events,'collect',side_effect=lambda source,*args:[self.actual] if source.city=='静岡市' else []),patch.object(
            ai_rewriter,'rewrite_collected_events',return_value=[{'summary':'2098年1月1日開催','description':'案内'}]),patch.dict('os.environ',{'GEMINI_API_KEY':'test'}):
            self.assertEqual(collect_events.main(['--db',str(self.db),'--max-rechecks','0']),1)
        self.assertEqual(self.db.read_bytes(),before)
    def test_stale_record_aborts_correction(self):
        corrections,_=self.plan()
        with sqlite3.connect(self.db) as c:
            c.execute('UPDATE events SET title=? WHERE id=?',('他の人の修正',self.id));c.commit()
            with self.assertRaises(ValueError):
                collect_events.save_events(c,corrections,[{'summary':'案内','description':'説明'}])
            self.assertEqual(c.execute('SELECT title FROM events WHERE id=?',(self.id,)).fetchone()[0],'他の人の修正')
