import datetime as dt
import sqlite3
import unittest
from unittest.mock import patch
from collect_shizuoka_calendar import detail_record,calendar_links,save
from publication_gate import FIELDS,approved_rows
URL='https://www.city.shizuoka.lg.jp/s6725/s013125.html'
TODAY=dt.date(2026,10,21)
# Representative table fixture based on fields seen on the official page, not downloaded HTML.
HTML='''<h1>企画展</h1><table><tr><th>年月日</th><td><ul><li>2026年10月10日（土曜日）から2026年11月29日（日曜日）</li></ul></td></tr><tr><th>時間</th><td>9時～18時</td></tr><tr><th>備考</th><td>月曜日休館（祝日の場合は翌平日休館）</td></tr></table><table><tr><th>開催場所</th><td>静岡市歴史博物館</td></tr></table>'''
class ShizuokaCalendarTests(unittest.TestCase):
    def test_only_facts_no_prose_photos_or_inferred_services(self):
        row=detail_record(URL,HTML+'<p>架空の紹介文</p><img src="example.jpg">',TODAY)
        self.assertEqual(row['location'],'静岡市歴史博物館')
        self.assertIn('月曜日休館',row['date_str'])
        self.assertNotIn('架空',row['description'])
        self.assertEqual(row['image_url'],'')
        self.assertEqual(row['lat'],0)
    def test_ambiguous_missing_expired_and_cancelled_are_held(self):
        for html in [HTML.replace('2026年','2025年'),HTML.replace('開催場所','アクセス'),HTML.replace('企画展','開催中止'),HTML.replace('から','・'),HTML.replace('</ul>','<li>2026年12月1日</li></ul>'),HTML.replace('2026年11月29日','2026年99月99日')]:
            with self.assertRaises(ValueError):detail_record(URL,html,TODAY)
    def test_only_same_host_table_links(self):
        text=f'<a href="/s111/s222.html">navigation</a><table><tr><td><a href="{URL}">event</a><a href="https://example.com/s1/s2.html">external</a></td></tr></table>'
        self.assertEqual(calendar_links(text),[URL])
        with self.assertRaises(ValueError):detail_record('https://example.com/s1/s2.html',HTML,TODAY)
    def test_save_publication_hash_and_failed_recheck(self):
        c=sqlite3.connect(':memory:')
        c.execute('CREATE TABLE events(id INTEGER PRIMARY KEY,'+','.join(k+' '+('INTEGER' if k.startswith('is_') else 'REAL' if k in ('lat','lng') else 'TEXT') for k in FIELDS)+')')
        row=detail_record(URL,HTML,TODAY);now=dt.datetime(2026,10,21,tzinfo=dt.timezone.utc)
        with patch('publication_gate.reviews',return_value=[]):
            self.assertEqual(len(save(c,[(URL,row,'a'*64)],[URL],now)),1)
            rows=c.execute('select * from events').fetchall()
            self.assertEqual(len(approved_rows(c,rows,TODAY)),1)
            save(c,[(URL,row,'a'*64)],[URL],now)
            self.assertEqual(c.execute('select count(*) from events').fetchone()[0],1)
            c.execute("update events set fee='無料'")
            self.assertEqual(approved_rows(c,c.execute('select * from events').fetchall(),TODAY),[])
            save(c,[],[URL],now)
            self.assertEqual(c.execute('select count(*) from city_calendar_publication').fetchone()[0],0)
        c.close()
if __name__=='__main__':unittest.main()
