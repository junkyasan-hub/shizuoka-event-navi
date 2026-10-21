from db_fixture import create_test_db
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import manual_events as manual
import generate_site

class ManualTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:')
        create_test_db(self.conn)
        self.conn.row_factory=sqlite3.Row
        self.row=dict(self.conn.execute("SELECT * FROM events WHERE item_type='event' LIMIT 1").fetchone())
    def tearDown(self): self.conn.close()
    def change(self,action='edit',fields=None):
        return dict(action=action,id=self.row['id'],version=manual.fingerprint(self.row),fields=fields or {})
    def test_conflict_and_invalid_date_leave_data(self):
        for change in (dict(self.change(),version='old'),self.change(fields={'date_str':'2026年2月30日'}),self.change(fields={'official_url':'javascript:alert(1)'})):
            with self.assertRaises(ValueError): manual.apply(self.conn,change)
        self.assertEqual(dict(self.conn.execute('SELECT * FROM events WHERE id=?',(self.row['id'],)).fetchone()),self.row)
    def test_edit_history_and_protection(self):
        manual.apply(self.conn,self.change(fields={'title':'確認済みのイベント'}))
        self.assertIn(self.row['id'],manual.controls(self.conn))
        history=self.conn.execute('SELECT before_json FROM event_manual_history ORDER BY rowid DESC LIMIT 1').fetchone()[0]
        self.assertEqual(json.loads(history),self.row)
        with self.assertRaises(ValueError):manual.apply(self.conn,self.change(fields={'title':'古い画面'}))
    def test_hide_restore_and_editor(self):
        manual.apply(self.conn,self.change('hide'))
        with tempfile.TemporaryDirectory() as temp:
            db=Path(temp)/'test.db'
            with sqlite3.connect(db) as dest:self.conn.backup(dest)
            with patch.object(generate_site,'DB_PATH',str(db)):
                self.assertNotIn(self.row['id'],[r['id'] for r in generate_site.fetch_events()])
            manual.build_editor(self.conn,Path(temp)/'editor.html')
            content=(Path(temp)/'editor.html').read_text()
            self.assertNotIn('__EVENT_DATA__',content)
            self.assertIn('Apply Manual Event Change',content)
        manual.apply(self.conn,self.change('restore'))
        self.assertEqual(manual.controls(self.conn)[self.row['id']],0)
    def test_add(self):
        fields={k:self.row.get(k) or '' for k in manual.FIELDS}
        fields.update(title='追加テスト',date_str='2026年11月1日',official_url='https://example.org/event')
        event_id=manual.apply(self.conn,dict(action='add',fields=fields))
        self.assertEqual(self.conn.execute('SELECT title FROM events WHERE id=?',(event_id,)).fetchone()[0],'追加テスト')
