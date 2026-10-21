"""Publish factual Hamamatsu CC BY CSV records without AI-generated claims."""
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import sqlite3
from urllib.parse import quote
from zoneinfo import ZoneInfo

from event_sources import SOURCES, Fetcher, parse_hamamatsu, date_bounds
from publication_gate import FIELDS, fingerprint

SOURCE = SOURCES[0]
REQUIRED = {'NO','イベント名','開始日','終了日','カテゴリー','場所名称','住所',
            '料金(基本)','料金(詳細)','駐車場情報','URL','緯度','経度'}


def validated_records(content, today):
    raw = list(csv.DictReader(io.StringIO(content.decode('cp932'))))
    if not raw or not REQUIRED.issubset(raw[0]):
        raise ValueError('Empty CSV or required columns changed')
    ids = [r['NO'].strip() for r in raw]
    if any(not key for key in ids) or len(set(ids)) != len(ids):
        raise ValueError('Missing or duplicate source row IDs')
    events = parse_hamamatsu(SOURCE, content)
    accepted, held = [], []
    for event in events:
        bounds = date_bounds(event['date_str'])
        if not bounds or bounds[0] > bounds[1] or bounds[1] < today.isoformat():
            held.append({'title':event['title'],'reason':'invalid or expired date'})
            continue
        if not event['title'].strip() or event['location'] == '会場は出典をご確認ください':
            held.append({'title':event['title'],'reason':'missing title or venue'})
            continue
        notices = event['title'] + ' ' + event.get('source_notes','')
        if any(word in event['title'] for word in ('中止','延期')) or any(word in notices for word in ('開催中止','中止のお知らせ','開催延期','延期のお知らせ')):
            held.append({'title':event['title'],'reason':'cancellation or postponement requires review'})
            continue
        row = dict.fromkeys(FIELDS, '')
        row.update(item_type='event',title=event['title'],date_str=event['date_str'],
                   location=event['location'],city='浜松市',address=event['address'],
                   lat=event.get('lat',0.0),lng=event.get('lng',0.0),
                   google_maps_url='https://maps.google.com/?q='+quote(event['address']+' '+event['location']),
                   official_url=event['source_url'],tags='浜松市オープンデータ',
                   summary=event['title'],fee=event['fee'],parking_info=event['parking_info'],
                   organizer='主催・問い合わせ先は出典をご確認ください',
                   target_age='対象・参加条件は出典をご確認ください',
                   is_free_parking=0,is_stroller_ok=0,is_rainy_ok=0)
        facts=[('開催日',event['date_str']),('開催時間・注意事項',event.get('schedule_note','')),
               ('会場',event['location']),('住所',event['address']),('料金',event['fee']),
               ('駐車場',event['parking_info']),('説明・備考',event.get('source_notes',''))]
        row['description']='\n'.join(f'{label}：{value}' for label,value in facts if value)
        row['description']+='\n\n出典：浜松市イベントオープンデータ（CC BY 4.0）を加工\n'+event['source_url']
        accepted.append((event,row))
    return accepted,held


def sync(conn, content, fetched_at=None):
    fetched_at=fetched_at or dt.datetime.now(dt.timezone.utc)
    today=fetched_at.astimezone(ZoneInfo('Asia/Tokyo')).date()
    accepted,held=validated_records(content,today)
    # A valid but wholly unusable feed is held for investigation, not a mass withdrawal.
    if not accepted:
        raise ValueError('No valid current records; refusing to replace prior publication evidence')
    from manual_events import controls
    protected=controls(conn)
    conn.row_factory=sqlite3.Row
    identities = set()
    for ident in protected:
        existing = conn.execute('SELECT * FROM events WHERE id=?',(ident,)).fetchone()
        if existing:
            identities.add((existing['title'],existing['city'],date_bounds(existing['date_str'])))
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='event_manual_history'").fetchone():
        for before,after in conn.execute('SELECT before_json,after_json FROM event_manual_history'):
            for raw in (before,after):
                item=json.loads(raw)
                if item:
                    identities.add((item['title'],item['city'],date_bounds(item['date_str'])))
    saved=[]
    with conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS open_data_publication (
            source_key TEXT PRIMARY KEY,event_id INTEGER NOT NULL,record_hash TEXT NOT NULL,
            fetched_at TEXT NOT NULL,document_hash TEXT NOT NULL,evidence_json TEXT NOT NULL)''')
        conn.execute('DELETE FROM open_data_publication WHERE source_key LIKE ?', (SOURCE.url+'#%',))
        for event,row in accepted:
            existing=conn.execute('SELECT id FROM events WHERE official_url=? ORDER BY id LIMIT 1',(event['source_url'],)).fetchone()
            ident=existing['id'] if existing else None
            if ident in protected or (row['title'],row['city'],date_bounds(row['date_str'])) in identities:
                held.append({'title':row['title'],'reason':'manual protection'})
                continue
            vals=[row[k] for k in FIELDS]
            if ident is None:
                ident=conn.execute('INSERT INTO events ('+','.join(FIELDS)+') VALUES ('+','.join('?' for k in FIELDS)+')',vals).lastrowid
            else:
                conn.execute('UPDATE events SET '+','.join(k+'=?' for k in FIELDS)+' WHERE id=?', vals+[ident])
            conn.execute('INSERT INTO open_data_publication VALUES (?,?,?,?,?,?)',
                         (event['source_url'],ident,fingerprint(row),fetched_at.isoformat(),
                          hashlib.sha256(content).hexdigest(),json.dumps(event,ensure_ascii=False)))
            saved.append(ident)
    return {'source':SOURCE.url,'fetched_at':fetched_at.isoformat(),'saved':len(saved),'held':held}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',default='events.db')
    parser.add_argument('--backup',required=True)
    parser.add_argument('--report',required=True)
    args=parser.parse_args()
    if not Path(args.db).is_file() or Path(args.backup).exists():
        parser.error('Existing DB and new backup path required')
    try:
        content=Fetcher().get(SOURCE.url).content
        with sqlite3.connect(args.db) as conn:
            Path(args.backup).parent.mkdir(parents=True,exist_ok=True)
            with sqlite3.connect(args.backup) as backup: conn.backup(backup)
            report=sync(conn,content)
    except Exception as exc:
        report={'source':SOURCE.url,'status':'failed','error':str(exc),'saved':0}
        Path(args.report).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        raise
    Path(args.report).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Open data saved:',report['saved'],'held:',len(report['held']))

if __name__=='__main__': main()
