import copy
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import ai_rewriter
import collect_events
from event_sources import SOURCES, factual_event, date_bounds, parse_detail
from event_verification import (BodyVerificationError, check_body, recheck_published,
                                require_supported_bodies, save_rechecks, RECHECK_SOURCES)


class VerificationTests(unittest.TestCase):
    def event(self):
        event = factual_event(SOURCES[1], 'https://www.visit-shizuoka.com/event/detail_123456.html',
                              '検証イベント', '2099年10月18日', '会場A', fee='500円')
        event['schedule_note'] = '11:00〜11:30'
        return event

    def test_wrong_dates_times_prices_and_free_parking_are_held(self):
        result = check_body(self.event(), {'summary': '10月19日、14:00から。入場無料。無料駐車場あり。',
                                           'description': '料金は1,000円です。雨天決行。'})
        self.assertEqual(result['status'], 'needs_review')
        self.assertTrue(any('月日' in issue for issue in result['issues']))
        self.assertTrue(any('時刻' in issue for issue in result['issues']))
        self.assertTrue(any('料金' in issue for issue in result['issues']))
        self.assertTrue(any('駐車場' in issue for issue in result['issues']))
        self.assertTrue(any('雨天' in issue for issue in result['issues']))

    def test_supported_dates_times_and_fee_pass(self):
        result = check_body(self.event(), {'summary': '2099年10月18日に会場Aで開催。',
                                           'description': '午前11時から11:30まで。料金500円。'})
        self.assertEqual(result['issues'], [])

    def test_duration_parking_cost_and_licensed_deadline_are_not_false_alarms(self):
        event = self.event()
        event['parking_info'] = 'バスは2時間まで1,040円'
        event['source_notes'] = '申込締切は10月10日。雨天決行予定、荒天中止。'
        result = check_body(event, {'summary': '申込締切は10月10日。',
                                    'description': 'バス駐車は2時間まで1,040円。雨天決行予定、荒天中止。'})
        self.assertEqual(result['issues'], [])
        self.assertEqual(date_bounds('2026年11月4日 11:00〜11:30／14:00〜14:30'),
                         ('2026-11-04', '2026-11-04'))

    def test_existing_atami_page_includes_factual_program_times(self):
        event = parse_detail(RECHECK_SOURCES[-1], 'https://www.ataminews.gr.jp/event/148', '''
            <h1>もみじまつり</h1><h2>見出し</h2><p>【足湯】期間中10:00〜16:00</p>
            <table><tr><th>開催期間</th><td>2026年11/14～12/6</td></tr>
            <tr><th>開催時間</th><td>16:30〜21:00</td></tr><tr><th>会場名</th><td>熱海梅園</td></tr></table>''')
        self.assertEqual(event['title'], 'もみじまつり')
        self.assertEqual(check_body(event, {'summary': '足湯は10:00から16:00。', 'description': '点灯は16:30〜21:00。'})['issues'], [])

    def test_body_check_failure_blocks_entire_batch(self):
        with self.assertRaises(BodyVerificationError):
            require_supported_bodies([self.event()], [{'summary': '2099年10月19日開催', 'description': '案内'}])

    def test_weekday_is_checked_against_calendar(self):
        event = factual_event(SOURCES[1], 'https://example.invalid', '催事', '2026年10月31日', '会場')
        result = check_body(event, {'summary': '2026年10月31日(日)に開催', 'description': '案内'})
        self.assertTrue(any('曜日' in issue for issue in result['issues']))

    def test_deadline_year_is_not_invented_from_next_year_event(self):
        event = factual_event(SOURCES[1], 'https://example.invalid', '催事', '2027年1月10日', '会場')
        event['source_notes'] = '申込締切12月25日(金)'
        result = check_body(event, {'summary': '申込締切は12月25日(金)。', 'description': '案内'})
        self.assertEqual(result['issues'], [])

    def test_gemini_review_requires_real_source_quote(self):
        client = Mock()
        event = self.event()
        for verdict, quote in [('supported', '出典にない引用'), ('unsupported', event['title'])]:
            client.models.generate_content.return_value = SimpleNamespace(text=json.dumps({'items': [
                {'id': '0', 'verdict': verdict, 'issues': [], 'evidence': [{'field': 'title', 'quote': quote}]}]}))
            with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-only-key'}), patch.object(
                    ai_rewriter.genai, 'Client', return_value=client), self.assertRaises(BodyVerificationError):
                ai_rewriter.verify_rewritten_events([event], [{'summary': '紹介', 'description': '説明'}])

    def make_db(self, path):
        with sqlite3.connect(path) as conn:
            conn.execute('''CREATE TABLE events (id INTEGER PRIMARY KEY,title TEXT,date_str TEXT,
                location TEXT,city TEXT,summary TEXT,description TEXT,fee TEXT,official_url TEXT,item_type TEXT)''')
            event = self.event()
            conn.execute('INSERT INTO events VALUES (1,?,?,?,?,?,?,?,?,?)',
                         (event['title'], event['date_str'], event['location'], event['city'],
                          '検証イベントのご案内', '詳細は出典をご確認ください', '500円', event['source_url'], 'event'))
            conn.execute('CREATE TABLE event_imports (event_id INTEGER,source_key TEXT)')
            conn.execute('INSERT INTO event_imports VALUES (1,?)', (event['source_url'],))

    def test_date_change_and_cancellation_do_not_change_published_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'events.db'
            self.make_db(db)
            before = db.read_bytes()
            actual = self.event()
            actual['date_str'] = '2099年10月19日'
            actual['start_date'] = actual['end_date'] = '2099-10-19'
            with sqlite3.connect(db) as conn:
                checks = recheck_published(conn, [actual], {SOURCES[1].name}, Mock(), 0)
                self.assertEqual(checks[0]['status'], 'changed')
                self.assertIn('出典と開催日が異なる', checks[0]['issues'])
                actual['title'] = '【開催中止】検証イベント'
                checks = recheck_published(conn, [actual], {SOURCES[1].name}, Mock(), 0)
                self.assertEqual(checks[0]['status'], 'cancelled')
            self.assertEqual(db.read_bytes(), before)

    def test_timeout_is_unavailable_not_cancelled_or_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'events.db'
            self.make_db(db)
            fetcher = Mock()
            fetcher.get.side_effect = TimeoutError('timeout')
            with sqlite3.connect(db) as conn:
                result = recheck_published(conn, [], {SOURCES[1].name}, fetcher, 1)
                self.assertEqual(result[0]['status'], 'unavailable')
                self.assertEqual(conn.execute('SELECT count(*) FROM events').fetchone()[0], 1)

    def test_history_preserves_last_source_evidence_through_outage(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'events.db'
            self.make_db(db)
            with sqlite3.connect(db) as conn:
                checks = recheck_published(conn, [self.event()], {SOURCES[1].name}, Mock(), 0)
                self.assertEqual(checks[0]['status'], 'matched')
                save_rechecks(conn, checks)
                save_rechecks(conn, checks)
                self.assertEqual(conn.execute('SELECT count(*) FROM event_recheck_history').fetchone()[0], 1)
                unavailable = recheck_published(conn, [], set(), Mock(), 0)
                save_rechecks(conn, unavailable)
                self.assertIn('last_confirmed_source_facts', unavailable[0])
                actual = self.event();actual['schedule_note'] = '12:00〜12:30'
                changed = recheck_published(conn, [actual], {SOURCES[1].name}, Mock(), 0)
                self.assertEqual(changed[0]['source_changed_fields'], ['schedule_note'])

    def test_generic_homepage_and_request_limit_are_not_confirmations(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'events.db'
            self.make_db(db)
            with sqlite3.connect(db) as conn:
                checks = recheck_published(conn, [], {SOURCES[1].name}, Mock(), 0)
                self.assertEqual(checks[0]['status'], 'not_checked')
                conn.execute('DELETE FROM event_imports')
                conn.execute("UPDATE events SET official_url='https://www.visit-shizuoka.com/'")
                checks = recheck_published(conn, [], {SOURCES[1].name}, Mock(), 10)
                self.assertEqual(checks[0]['status'], 'needs_review')

    def test_conditional_weather_note_is_not_cancellation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'events.db'
            self.make_db(db)
            actual = self.event();actual['schedule_note'] = '11:00〜11:30 雨天中止'
            with sqlite3.connect(db) as conn:
                result = recheck_published(conn, [actual], {SOURCES[1].name}, Mock(), 0)
            self.assertEqual(result[0]['status'], 'matched')

    def test_legacy_title_can_match_a_new_cancellation_notice(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'events.db'
            self.make_db(db)
            actual = self.event();actual['title'] = '【開催中止】検証イベント'
            with sqlite3.connect(db) as conn:
                conn.execute('DELETE FROM event_imports')
                result = recheck_published(conn, [actual], {SOURCES[1].name}, Mock(), 0)
            self.assertEqual(result[0]['status'], 'cancelled')

    def test_main_holds_date_changes_instead_of_overwriting_or_duplicating(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'events.db';shutil.copy2('events.db', db)
            original = self.event()
            with sqlite3.connect(db) as conn:
                collect_events.save_events(conn, [(original, None)], [{'summary': '案内', 'description': '説明'}])
                before = conn.execute('SELECT * FROM events ORDER BY id').fetchall()
            actual = copy.deepcopy(original)
            actual['date_str'] = actual['source_date_str'] = '2099年10月19日'
            actual['start_date'] = actual['end_date'] = '2099-10-19'
            report_path = Path(tmp) / 'report.json'
            with patch.object(collect_events, 'collect', side_effect=lambda source, *args:
                              [actual] if source.city == actual['city'] else []):
                code = collect_events.main(['--db', str(db), '--max-rechecks', '0', '--no-rewrite',
                                           '--allow-partial', '--output', str(report_path)])
            self.assertEqual(code, 0)
            report = json.loads(report_path.read_text())
            self.assertEqual(report['saved'], 0)
            self.assertEqual(len(report['held_updates']), 1)
            with sqlite3.connect(db) as conn:
                self.assertEqual(conn.execute('SELECT * FROM events ORDER BY id').fetchall(), before)

    def test_main_does_not_save_bad_generated_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'events.db';shutil.copy2('events.db', db)
            before = db.read_bytes();event = self.event()
            report_path = Path(tmp) / 'report.json'
            with patch.object(collect_events, 'collect', side_effect=lambda source, *args:
                              [event] if source.city == event['city'] else []), patch.object(
                    ai_rewriter, 'rewrite_collected_events', return_value=[{'summary': '2099年10月19日開催', 'description': '案内'}]), patch.dict(
                    'os.environ', {'GEMINI_API_KEY': 'test-only-key'}):
                code = collect_events.main(['--db', str(db), '--max-rechecks', '0', '--output', str(report_path)])
            self.assertEqual(code, 1)
            self.assertEqual(db.read_bytes(), before)
            report = json.loads(report_path.read_text())
            self.assertEqual(report['body_verification'], 'needs_review')
            self.assertEqual(report['saved'], 0)


if __name__ == '__main__':
    unittest.main()
