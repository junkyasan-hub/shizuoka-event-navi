"""Reviewed manual changes, optimistic locking, and persistent publication controls."""
import datetime
import hashlib
import json
import sqlite3
from pathlib import Path

FIELDS = {'title':'イベント名','date_str':'開催日（例：2026年11月1日）','city':'市町村','location':'会場','address':'住所','official_url':'公式ページURL','summary':'紹介文（短文）','description':'本文','fee':'料金','organizer':'主催者','parking_info':'駐車場','tags':'タグ','target_age':'対象年齢'}

def fingerprint(row):
    return hashlib.sha256(json.dumps(dict(row), ensure_ascii=False, sort_keys=True).encode()).hexdigest()

def controls(conn):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='event_manual_controls'").fetchone():
        return {}
    return {r[0]:r[1] for r in conn.execute('SELECT event_id,hidden FROM event_manual_controls')}

def apply(conn, change):
    if change.get('action') not in ('edit','hide','restore','add'):
        raise ValueError('操作が不正です')
    action = change['action']
    request_hash = hashlib.sha256(json.dumps(change, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='event_manual_requests'").fetchone():
        prior = conn.execute('SELECT event_id FROM event_manual_requests WHERE request_hash=?',(request_hash,)).fetchone()
        if prior:
            return prior[0]
    conn.row_factory = sqlite3.Row
    row = None if action == 'add' else conn.execute('SELECT * FROM events WHERE id=?',(change.get('id'),)).fetchone()
    if action != 'add' and (not row or fingerprint(row) != change.get('version')):
        raise ValueError('データが更新されています。最新の編集画面を開き直してください')
    values = change.get('fields', {})
    if not isinstance(values, dict) or set(values) - set(FIELDS):
        raise ValueError('編集項目が不正です')
    for k,v in values.items():
        if not isinstance(v,str) or len(v)>12000 or '<' in v or '>' in v:
            raise ValueError('本文はHTMLを使わず、12000文字以内で入力してください')
        if k == 'official_url' and v and not v.startswith(('https://','http://')):
            raise ValueError('公式URLはhttps://またはhttp://で始めてください')
    merged = dict(row) if row else {}
    merged.update(values)
    if action in ('add','edit'):
        if any(not merged.get(k,'').strip() for k in ('title','date_str','city','location','official_url')):
            raise ValueError('イベント名・開催日・市町村・会場・公式URLは必須です')
        from event_sources import date_bounds
        import re
        bounds = date_bounds(merged['date_str'])
        if not bounds or not re.match(r'^20\d{2}年\d{1,2}月\d{1,2}日', merged['date_str']):
            raise ValueError('開催日は2026年11月1日の形式で実在する日付を入力してください')
    with conn:
        conn.execute('CREATE TABLE IF NOT EXISTS event_manual_requests (request_hash TEXT PRIMARY KEY, event_id INTEGER NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS event_manual_controls (event_id INTEGER PRIMARY KEY, hidden INTEGER NOT NULL DEFAULT 0)')
        conn.execute('CREATE TABLE IF NOT EXISTS event_manual_history (changed_at TEXT, event_id INTEGER, action TEXT, before_json TEXT, after_json TEXT)')
        if action == 'add':
            defaults = dict(item_type='event',title='',date_str='',city='',location='',tags='',summary='',description='',image_url='',fee='',organizer='')
            defaults.update(values)
            keys = list(defaults)
            event_id = conn.execute(f'INSERT INTO events ({",".join(keys)}) VALUES ({",".join("?" for _ in keys)})',list(defaults.values())).lastrowid
        else:
            event_id = row['id']
            if action == 'edit' and values:
                conn.execute(f'UPDATE events SET {",".join(k+"=?" for k in values)} WHERE id=?',(*values.values(),event_id))
        if action in ('add', 'edit') and (action == 'add' or set(values) & {'city','location','address'}):
            from urllib.parse import quote
            place = ' '.join(str(merged.get(k,'')) for k in ('city','location','address'))
            conn.execute('UPDATE events SET google_maps_url=?,lat=0,lng=0 WHERE id=?',('https://maps.google.com/?q='+quote(place),event_id))
        conn.execute('INSERT INTO event_manual_requests VALUES (?,?)',(request_hash,event_id))
        hidden = 1 if action == 'hide' else (controls(conn).get(event_id,0) if action=='edit' else 0)
        conn.execute('INSERT OR REPLACE INTO event_manual_controls VALUES (?,?)',(event_id,hidden))
        after = dict(conn.execute('SELECT * FROM events WHERE id=?',(event_id,)).fetchone())
        conn.execute('INSERT INTO event_manual_history VALUES (?,?,?,?,?)',(datetime.datetime.now(datetime.timezone.utc).isoformat(),event_id,action,json.dumps(dict(row) if row else None,ensure_ascii=False),json.dumps(after,ensure_ascii=False)))
    return event_id

def build_editor(conn, output):
    conn.row_factory = sqlite3.Row
    flags = controls(conn)
    rows = [dict(r) for r in conn.execute('SELECT * FROM events ORDER BY id DESC')]
    for row in rows:
        row['version'] = fingerprint(row)
        row['hidden'] = flags.get(row['id'],0)
    template = Path('templates/manual_editor.html').read_text()
    data = json.dumps({'rows':rows,'fields':FIELDS},ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    Path(output).write_text(template.replace('__EVENT_DATA__',data),encoding='utf-8')

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--change',required=True)
    parser.add_argument('--db',default='events.db')
    parser.add_argument('--backup',required=True)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        Path(args.backup).parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(args.backup) as backup:
            conn.backup(backup)
        print('変更したイベントID:',apply(conn,json.loads(Path(args.change).read_text())))
