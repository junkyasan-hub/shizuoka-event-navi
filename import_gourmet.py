"""Import individually checked restaurant facts; never overwrite existing records."""
import argparse
import datetime
import json
from pathlib import Path
import sqlite3
from urllib.parse import quote, urlsplit


def import_restaurants(conn, records):
    added = []
    with conn:
        for row in records:
            for field in ('title', 'city', 'address', 'hours', 'closed', 'source_url', 'checked_on'):
                if not isinstance(row.get(field), str) or not row[field].strip():
                    raise ValueError(f'Missing field: {field}')
            datetime.date.fromisoformat(row['checked_on'])
            url = urlsplit(row['source_url'])
            if url.scheme != 'https' or url.hostname != 'itospa.com' or not url.path.startswith('/gourmet/detail_'):
                raise ValueError('Unreviewed source URL')
            prior = conn.execute(
                'SELECT id FROM events WHERE official_url=? OR (city=? AND title=?)',
                (row['source_url'], row['city'], row['title'])).fetchone()
            if prior:
                continue
            summary = f"{row['city']}の常設飲食店。所在地：{row['address']}。"
            description = (f"{summary}\n営業時間：{row['hours']}\n定休日：{row['closed']}\n"
                           f"情報元：伊豆・伊東観光ガイド\n{row['source_url']}\n"
                           f"情報元確認日：{row['checked_on']}\n"
                           '観光サイトの掲載情報を確認した日付です。営業状況・価格は来店前に店舗へご確認ください。')
            values = dict(item_type='gourmet', title=row['title'], city=row['city'],
                          address=row['address'], location=row['title'],
                          date_str=f"{row['hours']}／定休日：{row['closed']}",
                          official_url=row['source_url'], tags=row.get('tags', 'グルメ,常設飲食店'),
                          summary=summary, description=description, image_url='',
                          fee='メニュー・価格は情報元または店舗へご確認ください',
                          organizer=row['title'], parking_info=row.get('parking', '情報元をご確認ください'),
                          target_age='店舗へご確認ください', category_scene='',
                          google_maps_url='https://maps.google.com/?q='+quote(row['address']+' '+row['title']))
            columns = ','.join(values)
            placeholders = ','.join('?' for _ in values)
            cursor = conn.execute(f'INSERT INTO events ({columns}) VALUES ({placeholders})', list(values.values()))
            added.append(cursor.lastrowid)
    return added


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='events.db')
    parser.add_argument('--input', default='gourmet_seed.json')
    parser.add_argument('--backup', required=True, help='New backup file; never overwrites an existing backup')
    args = parser.parse_args()
    if Path(args.backup).exists():
        parser.error('Backup already exists')
    if not Path(args.db).is_file():
        parser.error('Database does not exist')
    records = json.loads(Path(args.input).read_text(encoding='utf-8'))
    Path(args.backup).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(args.db) as conn:
        with sqlite3.connect(args.backup) as backup:
            conn.backup(backup)
        print('追加した飲食店ID:', import_restaurants(conn, records))
