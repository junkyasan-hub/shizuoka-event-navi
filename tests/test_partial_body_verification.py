"""A rejected event must not block unrelated verified imports."""
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
from event_sources import SOURCES, factual_event

class PartialBodyTests(unittest.TestCase):
    def events(self):
        return [factual_event(SOURCES[1], f'https://www.visit-shizuoka.com/event/detail_{990000+i}.html',
                              '検証用イベント'+str(i), '2099年10月18日', '会場') for i in range(2)]
    def responses(self,events):
        return [SimpleNamespace(text=json.dumps({'items':[
            {'id':str(i),'summary':'イベントのご案内','description':'詳細は出典をご確認ください。'} for i in range(2)]})),
            SimpleNamespace(text=json.dumps({'items':[
            {'id':'0','verdict':'supported','issues':[],'evidence':[{'field':'title','quote':events[0]['title']}]},
            {'id':'1','verdict':'supported','issues':[],'evidence':[{'field':'title','quote':'元情報にない引用'}]}]}))]
    def test_valid_event_saved_and_bad_quote_reported_with_body_and_facts(self):
        events=self.events();client=Mock()
        client.models.generate_content.side_effect=self.responses(events)
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'events.db';shutil.copy2('events.db',db)
            report=Path(tmp)/'report.json';summary=Path(tmp)/'summary.md'
            with sqlite3.connect(db) as conn:before=conn.execute('SELECT * FROM events ORDER BY id').fetchall()
            with patch.object(collect_events,'collect',side_effect=lambda source,*args:events if source.city=='静岡市' else []),patch.object(
                collect_events,'recheck_published',return_value=[]),patch.object(ai_rewriter.genai,'Client',return_value=client),patch.dict(
                'os.environ',{'GEMINI_API_KEY':'test-key-not-to-be-reported','GITHUB_STEP_SUMMARY':str(summary)}):
                code=collect_events.main(['--db',str(db),'--max-rechecks','0','--output',str(report)])
            self.assertEqual(code,0)
            result=json.loads(report.read_text())
            self.assertEqual((result['status'],result['saved'],result['body_held']),('partial',1,1))
            held=result['body_issues'][0]
            self.assertEqual(held['source_facts']['title'],events[1]['title'])
            self.assertEqual(held['body']['summary'],'イベントのご案内')
            self.assertEqual(held['gemini_review']['evidence'][0]['quote'],'元情報にない引用')
            self.assertIn('引用が一致',held['issues'][0])
            self.assertNotIn('test-key-not-to-be-reported',report.read_text())
            self.assertIn('本文の保留理由',summary.read_text())
            with sqlite3.connect(db) as conn:
                after=conn.execute('SELECT * FROM events ORDER BY id').fetchall()
                self.assertEqual(after[:len(before)],before)
                self.assertEqual(len(after),len(before)+1)
                self.assertEqual(after[-1][2],events[0]['title'])
    def test_deterministic_failure_is_held_even_if_gemini_approves(self):
        events=self.events();bodies=[{'summary':'2098年1月1日開催','description':'案内'}, {'summary':'案内','description':'説明'}]
        reviews=[{'id':str(i),'verdict':'supported','issues':[],'evidence':[{'field':'title','quote':e['title']}]} for i,e in enumerate(events)]
        client=Mock();client.models.generate_content.return_value=SimpleNamespace(text=json.dumps({'items':reviews}))
        with patch.object(ai_rewriter.genai,'Client',return_value=client),patch.dict('os.environ',{'GEMINI_API_KEY':'test'}):
            result=ai_rewriter.verify_rewritten_events(events,bodies,allow_partial=True)
        self.assertTrue(result[0]['_issues'])
        self.assertEqual(result[1]['_issues'],[])
    def test_invalid_or_missing_id_blocks_whole_batch_and_preserves_diagnostics(self):
        client=Mock()
        for response in ('not json','{"items":[]}', '{"items":[{"id":"0"},{"id":"0"}]}'):
            client.models.generate_content.return_value=SimpleNamespace(text=response)
            with patch.object(ai_rewriter.genai,'Client',return_value=client),patch.dict('os.environ',{'GEMINI_API_KEY':'test'}):
                with self.assertRaises(RuntimeError) as caught:
                    ai_rewriter.verify_rewritten_events(self.events(),[{'summary':'案内','description':'説明'}]*2,allow_partial=True)
            self.assertEqual(caught.exception.verification_diagnostics['review_response'],response)
    def test_all_rejected_or_invalid_item_evidence_is_never_approved(self):
        for evidence in ([],[None],[{'field':[], 'quote':'a'}],[{'field':'title','quote':''}]):
            client=Mock();events=self.events()
            client.models.generate_content.return_value=SimpleNamespace(text=json.dumps({'items':[
                {'id':str(i),'verdict':'uncertain','issues':['根拠不足'],'evidence':evidence} for i in range(2)]}))
            with patch.object(ai_rewriter.genai,'Client',return_value=client),patch.dict('os.environ',{'GEMINI_API_KEY':'test'}):
                results=ai_rewriter.verify_rewritten_events(events,[{'summary':'案内','description':'説明'}]*2,allow_partial=True)
            self.assertTrue(all(r['_issues'] for r in results))
