import copy
import contextlib
import io
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
import generate_site
from event_sources import SOURCES, Fetcher, date_bounds, factual_event, parse_detail, parse_shimoda


class CollectionTests(unittest.TestCase):
    def event(self):
        return factual_event(SOURCES[1], 'https://www.visit-shizuoka.com/event/detail_99999.html',
                             'テスト催事', '2099年10月18日', '清水マリンパーク', fee='無料')

    def test_explicit_year_and_date_validation(self):
        self.assertIsNone(date_bounds('毎年10月18日'))
        self.assertIsNone(date_bounds('2026年2月30日'))
        self.assertEqual(date_bounds('2026年12月30日〜1月3日'), ('2026-12-30', '2027-01-03'))
        self.assertEqual(date_bounds('2026年11/14～12/6'), ('2026-11-14', '2026-12-06'))

    def test_discrete_days_not_mistaken_for_continuous_period(self):
        event = factual_event(SOURCES[1], 'https://example.invalid', '催事', '2026年10月18日・25日')
        self.assertEqual(event['end_date'], '')
        consecutive = factual_event(SOURCES[1], 'https://example.invalid', '催事', '2026年10月24日・25日')
        self.assertEqual(consecutive['date_str'], '2026年10月24日〜2026年10月25日')
        special = factual_event(SOURCES[1], 'https://example.invalid', '催事',
                                '2026年9月3日(木)~11月30日(月)の特定日')
        self.assertEqual(special['end_date'], '')
        note = factual_event(SOURCES[1], 'https://example.invalid', '催事',
                             '2026年12月5日～2027年1月3日（期間中は売店・駐車場あり）')
        self.assertEqual(note['end_date'], '2027-01-03')

    def test_html_uses_facts_not_marketing_copy(self):
        html = '''<h1 class="title">展覧会</h1><p>転載しない独自の紹介文</p><table>
        <tr><th>イベント開催期間</th><td>2026年10月27日（火）～11月1日（日）</td></tr>
        <tr><th>イベント会場名</th><td>会場A</td></tr>
        <tr><th>料金</th><td>無料</td></tr></table>'''
        event = parse_detail(SOURCES[2], 'https://numazukanko.jp/event/1', html)
        self.assertEqual(event['end_date'], '2026-11-01')
        self.assertEqual(event['location'], '会場A')
        self.assertNotIn('転載しない', json.dumps(event, ensure_ascii=False))

    def test_shimoda_separate_headings_and_cross_year_dates(self):
        html = '''<div data-testid="richTextElement" id="comp-a"><h3>アロエの里</h3>
        <h3>2026年12月5日～2027年1月3日<br/>紹介文は取り込まない</h3></div>'''
        events = parse_shimoda(SOURCES[-1], html)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['end_date'], '2027-01-03')
        self.assertTrue(events[0]['source_url'].endswith('#comp-a'))

    def test_import_idempotency_updates_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'events.db'
            shutil.copy2('events.db', path)
            with sqlite3.connect(path) as conn:
                count = conn.execute('SELECT COUNT(*) FROM events').fetchone()[0]
                event = self.event()
                selected = collect_events.pending_events(conn, [event, copy.deepcopy(event)])
                self.assertEqual(len(selected), 1)
                rewrite = {'summary': 'Geminiの紹介文', 'description': '基本情報に基づく説明'}
                collect_events.save_events(conn, selected, [rewrite])
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM events').fetchone()[0], count + 1)
                self.assertEqual(collect_events.pending_events(conn, [event]), [])
                event['fee'] = '100円'
                selected = collect_events.pending_events(conn, [event])
                self.assertIsNotNone(selected[0][1])
                collect_events.save_events(conn, selected, [rewrite])
                row = conn.execute('SELECT fee,description,is_free_parking FROM events WHERE id=?',
                                   (selected[0][1],)).fetchone()
                self.assertEqual(row[0], '100円')
                self.assertIn(event['source_url'], row[1])
                self.assertEqual(row[2], 0)
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM events').fetchone()[0], count + 1)

    def test_existing_legacy_dates_do_not_duplicate(self):
        with sqlite3.connect(':memory:') as conn:
            conn.execute('CREATE TABLE events (id INTEGER, title TEXT,city TEXT,date_str TEXT,item_type TEXT)')
            event = self.event()
            conn.execute('INSERT INTO events VALUES (1,?,?,?,?)',
                         (event['title'], '静岡市', '2099年10月18日(日) 10:00〜12:00', 'event'))
            self.assertEqual(collect_events.pending_events(conn, [event]), [])

    def test_save_rolls_back_entire_import_on_later_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'events.db'
            shutil.copy2('events.db', db)
            with sqlite3.connect(db) as conn:
                count = conn.execute('SELECT COUNT(*) FROM events').fetchone()[0]
                had_imports = conn.execute("SELECT name FROM sqlite_master WHERE name='event_imports'").fetchone() is not None
                imports_before = conn.execute('SELECT * FROM event_imports ORDER BY source_key').fetchall() if had_imports else []
                first, invalid = self.event(), self.event()
                invalid['city'] = 'unsupported'
                rewrite = {'summary': '紹介', 'description': '説明'}
                with self.assertRaises(KeyError):
                    collect_events.save_events(conn, [(first, None), (invalid, None)], [rewrite, rewrite])
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM events').fetchone()[0], count)
                self.assertEqual(conn.execute(
                    "SELECT name FROM sqlite_master WHERE name='event_imports'").fetchone() is not None, had_imports)
                if had_imports:
                    self.assertEqual(conn.execute('SELECT * FROM event_imports ORDER BY source_key').fetchall(), imports_before)

    def test_gemini_plain_generation_and_fact_fields_unchanged(self):
        client = Mock()
        client.models.generate_content.return_value = SimpleNamespace(text=json.dumps({'items': [
            {'id': '0', 'summary': '紹介', 'description': '説明', 'title': '変更してはいけない'}]}))
        event = self.event()
        client.models.generate_content.side_effect = [client.models.generate_content.return_value,
            SimpleNamespace(text=json.dumps({'items': [{'id': '0', 'verdict': 'supported', 'issues': [],
                'evidence': [{'field': 'title', 'quote': event['title']}]}]}))]
        original = copy.deepcopy(event)
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-only-key'}), patch.object(
                ai_rewriter.genai, 'Client', return_value=client):
            result = ai_rewriter.rewrite_collected_events([event])
        self.assertEqual(result[0]['summary'], '紹介')
        self.assertEqual(result[0]['description'], '説明')
        self.assertEqual(result[0]['_body_verification']['method'], 'deterministic_and_gemini')
        self.assertEqual(event, original)
        self.assertEqual(client.models.generate_content.call_count, 2)
        config = client.models.generate_content.call_args.kwargs['config']
        self.assertFalse(config.tools)

    def test_gemini_error_or_invalid_json_does_not_fallback_to_success(self):
        client = Mock()
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-only-key'}), patch.object(
                ai_rewriter.genai, 'Client', return_value=client):
            client.models.generate_content.side_effect = RuntimeError('429')
            with self.assertRaises(RuntimeError):
                ai_rewriter.rewrite_collected_events([self.event()])
            client.models.generate_content.side_effect = None
            client.models.generate_content.return_value = SimpleNamespace(text='{"items":[]}')
            with self.assertRaises(RuntimeError):
                ai_rewriter.rewrite_collected_events([self.event()])

    def test_source_failure_no_writes_and_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'events.db'
            shutil.copy2('events.db', db)
            before = db.read_bytes()
            with patch.object(collect_events, 'collect', side_effect=RuntimeError('source down')):
                self.assertEqual(collect_events.main(['--max-rechecks', '0', '--db', str(db), '--no-rewrite']), 1)
            self.assertEqual(db.read_bytes(), before)

    def test_partial_collection_rewrites_other_sources_and_reports_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'events.db'
            report_path = Path(tmp) / 'report.json'
            summary_path = Path(tmp) / 'summary.md'
            shutil.copy2('events.db', db)
            with sqlite3.connect(db) as conn:
                before = conn.execute('SELECT COUNT(*) FROM events').fetchone()[0]

            def collect_source(source, fetcher, limit):
                if source.city == '沼津市':
                    raise TimeoutError('Read timed out (read timeout=30)')
                return [factual_event(source, source.url + '#2099-test',
                                      '2099年テスト催事-' + source.city, '2099年10月18日', '会場')]

            def rewrite(events, **kwargs):
                return [{'summary': 'Geminiで生成した紹介', 'description': '基本情報による説明'} for _ in events]

            output = io.StringIO()
            with patch.object(collect_events, 'collect', side_effect=collect_source), patch.object(
                    ai_rewriter, 'rewrite_collected_events', side_effect=rewrite) as rewrite_mock, patch.dict(
                    'os.environ', {'GEMINI_API_KEY': 'test-only-key', 'GITHUB_ACTIONS': 'true',
                                   'GITHUB_STEP_SUMMARY': str(summary_path)}), contextlib.redirect_stdout(output):
                code = collect_events.main(['--max-rechecks', '0', '--db', str(db), '--allow-partial', '--output', str(report_path)])
            self.assertEqual(code, 0)
            self.assertEqual(rewrite_mock.call_count, 1)
            self.assertEqual(len(rewrite_mock.call_args.args[0]), 4)
            report = json.loads(report_path.read_text())
            self.assertEqual(report['status'], 'partial')
            self.assertEqual(report['failed_sources'], ['沼津観光ポータル'])
            self.assertEqual(report['saved'], 4)
            self.assertIn('::warning', output.getvalue())
            self.assertIn('取得失敗', summary_path.read_text())
            with sqlite3.connect(db) as conn:
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM events').fetchone()[0], before + 4)

    def test_partial_mode_still_fails_when_all_sources_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'events.db'
            shutil.copy2('events.db', db)
            before = db.read_bytes()
            with patch.object(collect_events, 'collect', side_effect=TimeoutError('timeout')):
                self.assertEqual(collect_events.main(['--max-rechecks', '0', '--db', str(db), '--no-rewrite', '--allow-partial']), 1)
            self.assertEqual(db.read_bytes(), before)

    def test_partial_mode_does_not_hide_rewrite_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'events.db'
            report_path = Path(tmp) / 'report.json'
            shutil.copy2('events.db', db)
            before = db.read_bytes()

            def collect_source(source, fetcher, limit):
                if source.city == '沼津市':
                    raise TimeoutError('timeout')
                return [self.event()]

            with patch.object(collect_events, 'collect', side_effect=collect_source), patch.object(
                    ai_rewriter, 'rewrite_collected_events', side_effect=RuntimeError('Gemini HTTP 429')), patch.dict(
                    'os.environ', {'GEMINI_API_KEY': 'test-only-key'}):
                code = collect_events.main(['--max-rechecks', '0', '--db', str(db), '--allow-partial', '--output', str(report_path)])
            self.assertEqual(code, 1)
            self.assertEqual(db.read_bytes(), before)
            report = json.loads(report_path.read_text())
            self.assertEqual(report['status'], 'failed')
            self.assertEqual(report['saved'], 0)

    def test_robots_disallow_stops_requests(self):
        fetcher = Fetcher()
        response = Mock(status_code=200, text='User-agent: *\nDisallow: /event')
        with patch.object(fetcher, '_request', return_value=response) as request:
            with self.assertRaises(RuntimeError):
                fetcher.get('https://example.invalid/event/1')
            self.assertEqual(request.call_count, 1)

    def test_new_october_events_appear_in_static_calendar(self):
        item = {'id': 99999, 'title': '催事 </script>', 'start_iso': '2026-10-18',
                'end_iso': '2026-10-19', 'date_str': '2026年10月18日〜19日',
                'location': '会場', 'city': '静岡市', 'fee': '無料', 'organizer': '',
                'parking_info': '', 'summary': '紹介'}
        encoded = generate_site.extract_calendar_events([item])
        self.assertNotIn('</script>', encoded)
        calendar = json.loads(encoded)
        self.assertEqual(calendar[0]['start'], '2026-10-18')
        self.assertEqual(calendar[0]['end'], '2026-10-20')
        self.assertEqual(calendar[0]['extendedProps']['city'], '静岡市')


if __name__ == '__main__':
    unittest.main()
