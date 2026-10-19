from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from scripts import correct_verified_events as corrections


class VerifiedCorrectionsTests(unittest.TestCase):
    def make_db(self, path):
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('CREATE TABLE events (id INTEGER PRIMARY KEY, title TEXT, date_str TEXT)')
            conn.executemany('INSERT INTO events VALUES (?,?,?)', [
                (1, '修正するイベント', '2026年11月1日'),
                (840, '誤った日付の登録', '2026年10月19日'),
                (999, '未確認のため残すイベント', '2026年12月1日'),
            ])
            rows = {r['id']: r for r in conn.execute('SELECT * FROM events')}
            return [
                {'id': 1, 'action': 'update', 'expected_hash': corrections.row_hash(rows[1]),
                 'changes': {'date_str': '2026年10月31日'}},
                {'id': 840, 'action': 'delete', 'expected_hash': corrections.row_hash(rows[840])},
            ]

    def test_backup_targeted_changes_and_repeat_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'events.db'
            plan = self.make_db(db)
            with patch.object(corrections, 'PLAN', plan):
                result = corrections.apply_corrections(db, Path(tmp) / 'backup', Path(tmp) / 'events')
                self.assertEqual(result['updated'], [1])
                self.assertEqual(result['deleted'], [840])
                with sqlite3.connect(Path(result['backup']) / 'events-before.db') as backup:
                    self.assertIsNotNone(backup.execute('SELECT * FROM events WHERE id=840').fetchone())
                with sqlite3.connect(db) as conn:
                    self.assertIsNotNone(conn.execute('SELECT * FROM events WHERE id=999').fetchone())
                    self.assertEqual(conn.execute('SELECT date_str FROM events WHERE id=1').fetchone()[0], '2026年10月31日')
                page = (Path(tmp) / 'events/840.html').read_text()
                self.assertIn('noindex', page)
                self.assertIn('掲載情報を取り下げました', page)
                again = corrections.apply_corrections(db, Path(tmp) / 'backup')
                self.assertEqual(again['updated'], [])
                self.assertEqual(again['deleted'], [])
                self.assertEqual(again['already_applied'], [1, 840])

    def test_changed_record_stops_every_correction(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'events.db'
            plan = self.make_db(db)
            with sqlite3.connect(db) as conn:
                conn.execute('UPDATE events SET title=? WHERE id=840', ('利用者が変更した別イベント',))
            before = db.read_bytes()
            with patch.object(corrections, 'PLAN', plan), self.assertRaises(RuntimeError):
                corrections.apply_corrections(db, Path(tmp) / 'backup')
            self.assertEqual(db.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
