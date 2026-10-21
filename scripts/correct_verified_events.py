"""Apply the six source-verified corrections from the 2026-10-18 audit."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import sqlite3

PLAN = json.loads(r'''[
  {
    "id": 576,
    "action": "update",
    "expected_title": "アクト・プレミアム・シリーズ2026 ニコライ・ルガンスキー",
    "expected_date": "2027年2月16日(火) 18:45〜20:45",
    "expected_hash": "9280127311d9388cb504ad05b53ed0e8dd0b7cd567dbc1ceff0bb935666fe79b",
    "changes": {
      "title": "アクト・プレミアム・シリーズ2026　ニコライ・ルガンスキー(ピアノ)"
    },
    "evidence_url": "https://static.hamamatsu.odpf.net/opendata/v01/221309_hamamatsu_event/221309_hamamatsu_event.csv"
  },
  {
    "id": 580,
    "action": "update",
    "expected_title": "ミニコンサート「中世音楽アンサンブル」",
    "expected_date": "2026年11月4日(水) 14:00〜15:00",
    "expected_hash": "91d5b551ff65dfd1a3ed719c6aa2cea09b93415f886abdfa1b28334d97506cb5",
    "changes": {
      "title": "ミュージアムサロンコンサート「中世音楽アンサンブル」",
      "date_str": "2026年11月4日(水) 11:00〜11:30／14:00〜14:30",
      "summary": "浜松市楽器博物館で11月4日に開催する中世音楽アンサンブルの公演。出演はアモール・セウ。11:00〜11:30と14:00〜14:30の2回開催です。",
      "description": "2026年11月4日、浜松市楽器博物館でミュージアムサロンコンサート「中世音楽アンサンブル」が開催されます。\n出演：アモール・セウ\n開催時刻：11:00〜11:30／14:00〜14:30\n料金：入館料のみ\n\n出典：浜松市イベントオープンデータ NO=20260806036\nhttps://static.hamamatsu.odpf.net/opendata/v01/221309_hamamatsu_event/221309_hamamatsu_event.csv\n浜松市オープンデータを加工（CC BY 4.0）"
    },
    "evidence_url": "https://static.hamamatsu.odpf.net/opendata/v01/221309_hamamatsu_event/221309_hamamatsu_event.csv"
  },
  {
    "id": 591,
    "action": "update",
    "expected_title": "ハママツ・ジャズ・ウィーク　ストリート ジャズ フェスティバル",
    "expected_date": "2026年10月24日(土) 〜 10月25日(日)",
    "expected_hash": "a8b9219e586b5877f504b6ed5880c42418d330289d2ffcbb01e8f15f8f77c817",
    "changes": {
      "location": "24日…キタラ、ソラモ、クリエート浜松ホール　25日…キタラ、ソラモ、かじまちヤマハホール、新川モールほか"
    },
    "evidence_url": "https://static.hamamatsu.odpf.net/opendata/v01/221309_hamamatsu_event/221309_hamamatsu_event.csv"
  },
  {
    "id": 830,
    "action": "update",
    "expected_title": "大道芸ワールドカップ in 静岡 2026",
    "expected_date": "2026年11月1日(日) 〜 11月3日(火・祝) 10:00〜20:30",
    "expected_hash": "b2ee588a589e1601cbf6d8892d8fafbc4f5b3442134c71397904a5e48ecc3a4a",
    "changes": {
      "title": "大道芸ワールドカップ in 静岡2026",
      "date_str": "2026年10月31日(土)〜2026年11月3日(火・祝)",
      "location": "駿府城公園・静岡市中央体育館・静岡市街地ほか、イオンセントラルスクエア静岡、エスパルスドリームプラザ",
      "official_url": "https://www.visit-shizuoka.com/event/detail_690.html",
      "summary": "2026年10月31日から11月3日まで、静岡市内の各会場で開催される大道芸イベントです。公演ごとの時刻や観覧方法は公式情報をご確認ください。",
      "description": "開催日：2026年10月31日〜11月3日\n主な開催エリア：葵区（駿府城公園・静岡市中央体育館・市街地ほか）、駿河区（イオンセントラルスクエア静岡）、清水区（エスパルスドリームプラザ）。\n公演の開始時刻・料金・観覧方法は会場や公演ごとに公式情報をご確認ください。\n\n出典：静岡市観光ナビ\nhttps://www.visit-shizuoka.com/event/detail_690.html",
      "fee": "会場・公演の料金は出典をご確認ください",
      "parking_info": "駐車場の条件は出典をご確認ください",
      "is_stroller_ok": 0,
      "is_rainy_ok": 0
    },
    "evidence_url": "https://www.visit-shizuoka.com/event/detail_690.html"
  },
  {
    "id": 856,
    "action": "update",
    "expected_title": "熱海梅園 初秋のもみじまつり＆足湯体験",
    "expected_date": "2026年11月21日(土) 〜 12月6日(日) 8:30〜16:00",
    "expected_hash": "53732b06abb293053c25bd410ac9cfa5da2d63e260d32b74e27d53bae7484c5a",
    "changes": {
      "title": "第40回熱海梅園もみじまつり（2026）",
      "date_str": "2026年11月14日(土)〜2026年12月6日(日)",
      "location": "熱海梅園",
      "address": "静岡県熱海市梅園町8-11",
      "official_url": "https://www.ataminews.gr.jp/event/148",
      "summary": "2026年11月14日から12月6日まで熱海梅園で開催。期間中は足湯の開設や、夕方からのもみじライトアップが予定されています。",
      "description": "開催期間：2026年11月14日〜12月6日\n会場：熱海梅園（静岡県熱海市梅園町8-11）\n入園料：無料\n足湯：期間中10:00〜16:00\nもみじライトアップ：期間中16:30〜21:00\n天候等により日程や内容が変わる場合があります。最新情報は出典をご確認ください。\n\n出典：熱海市観光協会「あたみニュース」\nhttps://www.ataminews.gr.jp/event/148",
      "parking_info": "有料（普通車300円ほか。開設時間・車種別料金は出典をご確認ください）",
      "is_stroller_ok": 0,
      "is_rainy_ok": 0
    },
    "evidence_url": "https://www.ataminews.gr.jp/event/148"
  },
  {
    "id": 840,
    "action": "delete",
    "expected_title": "熱海海上花火大会 【2026年秋季公演】",
    "expected_date": "2026年10月19日(月) 20:20〜20:40",
    "expected_hash": "004eb5f361904cc219313ebf3913005669b0575f6de3ce463c3a2d7363a74cb5",
    "evidence_url": "https://www.ataminews.gr.jp/event/8",
    "reason": "登録された2026年10月19日は公式の2026年度開催日一覧に存在しない。別日の実在する花火大会は削除対象ではない。"
  }
]''')

RETIRED_PAGE = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,follow"><title>掲載情報を取り下げました</title>
</head><body><main><h1>掲載情報を取り下げました</h1>
<p>このページに掲載していた開催日を公式情報で確認できないため、掲載を取り下げました。</p>
<p>花火大会そのものの中止を示すものではありません。最新の開催日は主催者の公式情報をご確認ください。</p>
<p><a href="https://www.ataminews.gr.jp/event/8">熱海海上花火大会の公式情報</a></p>
<p><a href="../index.html">イベント一覧へ戻る</a></p></main></body></html>
"""


def row_hash(row):
    return hashlib.sha256(json.dumps(dict(row), ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def pending_changes(conn):
    changes, skipped = [], []
    for item in PLAN:
        row = conn.execute('SELECT * FROM events WHERE id=?', (item['id'],)).fetchone()
        if item['action'] == 'delete' and row is None:
            skipped.append(item['id'])
            continue
        if row is None:
            raise RuntimeError(f"ID {item['id']} is missing; refusing to guess a replacement")
        if item['action'] == 'update' and all(row[key] == value for key, value in item['changes'].items()):
            skipped.append(item['id'])
            continue
        if row_hash(row) != item['expected_hash']:
            raise RuntimeError(f"ID {item['id']} changed since audit; database not modified")
        changes.append((item, dict(row)))
    return changes, skipped


def apply_corrections(db_path, backup_dir, retired_dir=None):
    db_path = Path(db_path).resolve()
    if not db_path.is_file():
        raise RuntimeError('Database must already exist')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    backup_path = None
    try:
        changes, skipped = pending_changes(conn)
        if changes:
            stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            backup_path = Path(backup_dir) / stamp
            backup_path.mkdir(parents=True, exist_ok=False)
            with sqlite3.connect(backup_path / 'events-before.db') as backup:
                conn.backup(backup)
            with conn:
                conn.execute('BEGIN IMMEDIATE')
                # Recheck under the write lock before touching any record.
                changes, skipped = pending_changes(conn)
                for item, old in changes:
                    if item['action'] == 'delete':
                        conn.execute('DELETE FROM events WHERE id=?', (item['id'],))
                        if conn.execute("SELECT name FROM sqlite_master WHERE name='event_imports'").fetchone():
                            conn.execute('DELETE FROM event_imports WHERE event_id=?', (item['id'],))
                    else:
                        fields = list(item['changes'])
                        conn.execute('UPDATE events SET ' + ','.join(field + '=?' for field in fields) + ' WHERE id=?',
                                     [item['changes'][field] for field in fields] + [item['id']])
            (backup_path / 'changed-records-before.json').write_text(
                json.dumps([old for _, old in changes], ensure_ascii=False, indent=2), encoding='utf-8')
        if retired_dir is not None:
            target = Path(retired_dir)
            target.mkdir(parents=True, exist_ok=True)
            # The existing ZIP deploy cannot remove old server files. Replace the
            # removed detail page with a noindex withdrawal notice on every run.
            (target / '840.html').write_text(RETIRED_PAGE, encoding='utf-8')
        report = {
            'updated': [item['id'] for item, _ in changes if item['action'] == 'update'],
            'deleted': [item['id'] for item, _ in changes if item['action'] == 'delete'],
            'already_applied': skipped,
            'backup': str(backup_path) if backup_path else None,
            'unconfirmed_records_deleted': 0,
        }
        if backup_path:
            (backup_path / 'correction-report.json').write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        return report
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    parser.add_argument('--backup-dir', required=True)
    parser.add_argument('--retired-dir')
    args = parser.parse_args()
    print(json.dumps(apply_corrections(args.db, args.backup_dir, args.retired_dir),
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

