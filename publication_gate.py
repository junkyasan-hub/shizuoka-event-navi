"""Default-deny publication: exact reviewed content, dated sources, manual hides."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

MANIFEST = Path(__file__).with_name('reviewed_publication.json')
FIELDS = ('item_type','title','date_str','location','city','address','lat','lng',
          'google_maps_url','official_url','tags','summary','description','image_url',
          'fee','organizer','parking_info','target_age','is_free_parking',
          'is_stroller_ok','is_rainy_ok','category_scene')


def fingerprint(row):
    row = dict(row)
    return hashlib.sha256(json.dumps({k:row.get(k) for k in FIELDS}, ensure_ascii=False,
                                    sort_keys=True).encode()).hexdigest()


def reviews():
    # Missing/malformed evidence must never silently publish unreviewed data.
    data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if not isinstance(data, list):
        raise ValueError('Invalid publication manifest')
    return data


def approved_rows(conn, rows, today=None):
    from manual_events import controls
    hidden = controls(conn)
    today = today or dt.datetime.now(ZoneInfo('Asia/Tokyo')).date()
    approved = {}
    for item in reviews():
        checked = dt.date.fromisoformat(item['checked_on'])
        if not 0 <= (today-checked).days <= 7:
            continue
        if item['source_url'] != item['record']['official_url']:
            continue
        approved[fingerprint(item['record'])] = item
    automatic = {}
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='open_data_publication'").fetchone():
        for key, ident, digest, fetched_at in conn.execute('SELECT source_key,event_id,record_hash,fetched_at FROM open_data_publication'):
            try:
                fetched = dt.datetime.fromisoformat(fetched_at)
                checked = fetched.astimezone(ZoneInfo('Asia/Tokyo')).date()
                prefix = 'https://static.hamamatsu.odpf.net/opendata/v01/221309_hamamatsu_event/221309_hamamatsu_event.csv#'
                if fetched.tzinfo and key.startswith(prefix) and key[len(prefix):] and 0 <= (today-checked).days <= 7:
                    automatic[(ident,digest)] = {'checked_on':checked.isoformat(),'source_url':key}
            except (TypeError,ValueError):
                continue
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='city_calendar_publication'").fetchone():
        from urllib.parse import urlsplit
        import re
        for url, ident, digest, fetched_at in conn.execute('SELECT source_url,event_id,record_hash,fetched_at FROM city_calendar_publication'):
            try:
                fetched = dt.datetime.fromisoformat(fetched_at)
                checked = fetched.astimezone(ZoneInfo('Asia/Tokyo')).date()
                parts = urlsplit(url)
                if fetched.tzinfo and parts.scheme == 'https' and parts.netloc == 'www.city.shizuoka.lg.jp' and re.fullmatch(r'/s\d+/s\d+\.html',parts.path) and not parts.query and not parts.fragment and 0 <= (today-checked).days <= 7:
                    automatic[(ident,digest)] = {'checked_on':checked.isoformat(),'source_url':url}
            except (TypeError,ValueError):
                continue
    result = []
    for row in rows:
        row = dict(row)
        review = approved.get(fingerprint(row)) or automatic.get((row['id'],fingerprint(row)))
        if not review or hidden.get(row['id'], 0):
            continue
        row['verified_on'] = review['checked_on']
        row['verification_source'] = review['source_url']
        result.append(row)
    return result


def apply_reviewed(conn):
    """Only patch the exact previous snapshot; concurrent/manual edits are retained."""
    conn.row_factory = sqlite3.Row
    changed = []
    with conn:
        for item in reviews():
            if not item.get('replaces_hash'):
                continue
            for row in conn.execute('SELECT * FROM events WHERE official_url=?', (item['previous_url'],)).fetchall():
                if fingerprint(row) != item['replaces_hash']:
                    continue
                fields = item['record']
                conn.execute('UPDATE events SET '+','.join(k+'=?' for k in FIELDS)+' WHERE id=?',
                             [fields[k] for k in FIELDS]+[row['id']])
                changed.append(row['id'])
    return changed


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default='events.db')
    parser.add_argument('--backup', required=True)
    args = parser.parse_args()
    if not Path(args.db).is_file() or Path(args.backup).exists():
        parser.error('Existing database and new backup path required')
    Path(args.backup).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(args.db) as conn:
        with sqlite3.connect(args.backup) as backup:
            conn.backup(backup)
        print('Reviewed corrections:',apply_reviewed(conn))
        rows = conn.execute('SELECT * FROM events').fetchall()
        visible = approved_rows(conn, rows)
        print('Published:',len(visible),'Held:',len(rows)-len(visible))
