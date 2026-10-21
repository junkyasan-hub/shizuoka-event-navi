"""Synthetic database for tests. Never read or modify the deployment database."""
import sqlite3
from publication_gate import FIELDS


def record(**overrides):
    row=dict.fromkeys(FIELDS,'')
    row.update(item_type='event',title='テスト専用イベント',date_str='2099年1月1日',
               location='テスト会場',city='静岡市',official_url='https://example.invalid/test',
               lat=0.0,lng=0.0,is_free_parking=0,is_stroller_ok=0,is_rainy_ok=0)
    row.update(overrides)
    return row


def create_test_db(target):
    own=not isinstance(target,sqlite3.Connection)
    conn=sqlite3.connect(target) if own else target
    try:
        columns=['id INTEGER PRIMARY KEY AUTOINCREMENT']
        for key in FIELDS:
            kind='INTEGER' if key.startswith('is_') else 'REAL' if key in ('lat','lng') else 'TEXT'
            columns.append(f'{key} {kind}')
        columns.append('created_at TEXT DEFAULT CURRENT_TIMESTAMP')
        with conn:
            conn.execute('CREATE TABLE events ('+','.join(columns)+')')
            row=record()
            conn.execute('INSERT INTO events ('+','.join(FIELDS)+') VALUES ('+','.join('?' for _ in FIELDS)+')',[row[k] for k in FIELDS])
    finally:
        if own:conn.close()
