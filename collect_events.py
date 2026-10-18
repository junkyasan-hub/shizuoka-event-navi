"""Fetch official event facts, then rewrite them without a search API."""

import argparse
import collections
import datetime as dt
import hashlib
import json
import logging
import os
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

import ai_rewriter
from event_sources import SOURCES, Fetcher, clean, collect, date_bounds
from event_verification import (require_supported_bodies, recheck_published,
                                save_rechecks, BodyVerificationError, STATUS_LABELS, check_body)

LOG = logging.getLogger(__name__)
COORDS = {'浜松市': (34.7108, 137.7261), '静岡市': (34.9756, 138.3828),
          '沼津市': (35.1003, 138.8596), '伊東市': (34.9669, 139.0984),
          '下田市': (34.6781, 138.9453)}


def digest(event):
    return hashlib.sha256(json.dumps(event, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def source_key(event):
    # Dated Hamamatsu CSV row IDs distinguish occurrences. Tourism detail URLs
    # identify an event even when its date is corrected on the source site.
    return event['source_url']


def pending_events(conn, events):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    imports = {}
    if 'event_imports' in tables:
        imports = {r[0]: (r[1], r[2]) for r in conn.execute(
            'SELECT source_key, facts_hash, event_id FROM event_imports')}
    existing = {(clean(title), city, date_bounds(date)): event_id for event_id, title, city, date
                in conn.execute("SELECT id, title, city, date_str FROM events WHERE item_type='event'")}
    live_ids = {r[0] for r in conn.execute('SELECT id FROM events')}
    result = []
    seen = set()
    for event in events:
        key = source_key(event)
        identity = (clean(event['title']), event['city'], date_bounds(event['date_str']))
        if key in seen:
            continue
        seen.add(key)
        previous = imports.get(key)
        if previous and previous[1] in live_ids:
            if previous[0] != digest(event):
                result.append((event, previous[1]))
        elif identity not in existing:
            result.append((event, None))
            existing[identity] = None
    return result


def select_fairly(pending, limit):
    queues = collections.defaultdict(collections.deque)
    for event, event_id in sorted(pending, key=lambda pair: pair[0]['start_date']):
        queues[event['source_name']].append((event, event_id))
    selected = []
    while len(selected) < limit and any(queues.values()):
        for queue in queues.values():
            if queue and len(selected) < limit:
                selected.append(queue.popleft())
    return selected


def save_events(conn, selected, rewrites):
    """One transaction: a rewrite failure never leaves a partial import."""
    if len(selected) != len(rewrites):
        raise ValueError('rewrite count does not match selected events')
    require_supported_bodies([event for event, _ in selected], rewrites)
    fields = ('item_type', 'title', 'date_str', 'location', 'city', 'address', 'lat', 'lng',
              'google_maps_url', 'official_url', 'tags', 'summary', 'description', 'image_url',
              'fee', 'organizer', 'parking_info', 'target_age', 'is_free_parking',
              'is_stroller_ok', 'is_rainy_ok', 'category_scene')
    with conn:
        if not conn.in_transaction:
            conn.execute('BEGIN')
        conn.execute('''CREATE TABLE IF NOT EXISTS event_imports (
            source_key TEXT PRIMARY KEY, event_id INTEGER NOT NULL,
            facts_hash TEXT NOT NULL, source_name TEXT NOT NULL, fetched_at TEXT NOT NULL)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS event_body_checks (
            event_id INTEGER PRIMARY KEY, checked_at TEXT NOT NULL, verification_json TEXT NOT NULL)''')
        for (event, event_id), rewrite in zip(selected, rewrites):
            lat, lng = COORDS[event['city']]
            has_coordinates = 'lat' in event and 'lng' in event
            if has_coordinates:
                lat, lng = event['lat'], event['lng']
            # Keep the authoritative facts verbatim in the detail description,
            # even if the AI's wording contains an error. No AI field can replace them.
            facts = '\n'.join(f'{label}: {event.get(key, "")}' for label, key in (
                ('開催日', 'source_date_str'), ('開催時間・注意事項', 'schedule_note'), ('会場', 'location'),
                ('住所', 'address'), ('料金', 'fee'), ('駐車場', 'parking_info')))
            if not has_coordinates:
                facts += '\n地図のマーカーは市内の代表位置です。会場の正確な位置は出典をご確認ください。'
            attribution = f'出典: {event["source_name"]}\n{event["source_url"]}'
            if event['city'] == '浜松市':
                attribution += '\n浜松市オープンデータを加工（CC BY 4.0） https://creativecommons.org/licenses/by/4.0/'
            values = (
                'event', event['title'], event['date_str'], event['location'], event['city'],
                event['address'], lat, lng,
                f'https://maps.google.com/?q={event["city"]} {event["location"]}',
                event.get('official_url', event['source_url']),
                f'{event["city"]},イベント', rewrite['summary'],
                rewrite['description'] + '\n\n' + facts + '\n\n' + attribution,
                'https://images.unsplash.com/photo-1578637387939-43c525550085?auto=format&fit=crop&w=800&q=80',
                event['fee'], '出典をご確認ください', event['parking_info'],
                '出典をご確認ください', 0, 0, 0, '一般',
            )
            if event_id is None:
                event_id = conn.execute(
                    f'INSERT INTO events ({",".join(fields)}) VALUES ({",".join("?" for _ in fields)})',
                    values).lastrowid
            else:
                conn.execute(f'UPDATE events SET {",".join(f+"=?" for f in fields)} WHERE id=?',
                             (*values, event_id))
            conn.execute('''INSERT INTO event_imports VALUES (?,?,?,?,?)
                ON CONFLICT(source_key) DO UPDATE SET event_id=excluded.event_id,
                facts_hash=excluded.facts_hash, fetched_at=excluded.fetched_at''',
                         (source_key(event), event_id, digest(event), event['source_name'],
                          dt.datetime.now(dt.timezone.utc).isoformat()))
            verification = {
                'deterministic': check_body(event, rewrite),
                **rewrite.get('_body_verification', {'method': 'deterministic_only'}),
            }
            conn.execute('''INSERT INTO event_body_checks VALUES (?,?,?) ON CONFLICT(event_id)
                DO UPDATE SET checked_at=excluded.checked_at,verification_json=excluded.verification_json''',
                         (event_id, dt.datetime.now(dt.timezone.utc).isoformat(),
                          json.dumps(verification, ensure_ascii=False)))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='events.db')
    parser.add_argument('--dry-run', action='store_true', help='fetch only; no Gemini or database writes')
    parser.add_argument('--no-rewrite', action='store_true', help='explicit factual-text mode; no Gemini calls')
    parser.add_argument('--recheck-only', action='store_true', help='recheck published records; do not import or call Gemini')
    parser.add_argument('--max-rechecks', type=int, default=20, help='extra detail requests for published records')
    parser.add_argument('--allow-partial', action='store_true',
                        help='continue with successful sources, reporting failed sources as warnings')
    parser.add_argument('--max-events', type=int, default=20)
    parser.add_argument('--max-details', type=int, default=30, help='detail requests per HTML source, first listing page')
    parser.add_argument('--output', help='optional JSON report path (outside tracked dist recommended)')
    args = parser.parse_args(argv)
    if args.max_events < 1 or args.max_details < 1 or args.max_rechecks < 0:
        parser.error('limits must be positive')
    db_path = Path(args.db).resolve()
    if not db_path.is_file():
        parser.error('database must already exist; refusing to create an empty events.db')
    if not args.dry_run and not args.no_rewrite and not args.recheck_only and not os.environ.get('GEMINI_API_KEY'):
        LOG.error('GEMINI_API_KEY is missing; no database changes were made')
        return 1
    fetcher = Fetcher()
    today = dt.datetime.now(ZoneInfo('Asia/Tokyo')).date().isoformat()
    events, observed, failures, reports = [], [], [], []
    for source in SOURCES:
        try:
            found = collect(source, fetcher, args.max_details)
            observed.extend(found)
            dated = [e for e in found if e['end_date'] and e['end_date'] >= today
                     and not any(word in e['title'] + e['date_str'] for word in ('中止', '開催終了'))]
            # Unknown/recurring dates stay out of automatic publication.
            dated = [e for e in dated if not any(w in e['date_str'] for w in ('毎', '予定', '、', '・'))]
            events.extend(dated)
            reports.append({'source': source.name, 'parsed': len(found), 'eligible': len(dated)})
            LOG.info('%s: parsed=%d upcoming/ongoing=%d', source.name, len(found), len(dated))
        except Exception as exc:
            failures.append(source.name)
            reports.append({'source': source.name, 'error': str(exc)})
            LOG.error('%s: collection failed: %s', source.name, exc)
    with sqlite3.connect(f'{db_path.as_uri()}?mode=ro', uri=True) as conn:
        checks = recheck_published(conn, observed,
                                  {result['source'] for result in reports if 'error' not in result},
                                  fetcher, args.max_rechecks)
        pending = pending_events(conn, events)
    # A changed source must be reviewed before replacing an existing publication.
    held_ids = {item['event_id'] for item in checks if item['status'] != 'matched'}
    held_urls = {item['source_url'] for item in checks if item['status'] != 'matched'}
    held = [(event, event_id) for event, event_id in pending
            if event_id in held_ids or event['source_url'] in held_urls]
    pending = [(event, event_id) for event, event_id in pending
               if event_id not in held_ids and event['source_url'] not in held_urls]
    selected = select_fairly(pending, args.max_events)
    if args.recheck_only:
        selected = []
    report = {'sources': reports, 'eligible': len(events), 'pending': len(pending),
              'selected': [e for e, _ in selected], 'dry_run': args.dry_run, 'saved': 0,
              'failed_sources': failures.copy(), 'status': 'success'}
    check_counts = dict(collections.Counter(item['status'] for item in checks))
    report['published_recheck'] = {'counts': check_counts, 'results': checks}
    report['held_updates'] = [{'event_id': event_id, 'title': event['title'], 'source_url': event['source_url']}
                              for event, event_id in held]
    report['body_verification'] = 'not_run'
    report['recheck_only'] = args.recheck_only
    successful_sources = sum('error' not in result for result in reports)
    blocked = bool(failures) and (not args.allow_partial or not successful_sources)
    if blocked:
        LOG.error('Incomplete collection; refusing publication/database writes: %s', ', '.join(failures))
        report['status'] = 'failed'
    elif failures:
        report['status'] = 'partial'
        message = '一部の収集先で取得失敗。取得できた地域のみ処理します: ' + ', '.join(failures)
        LOG.warning(message)
        if os.environ.get('GITHUB_ACTIONS') == 'true':
            print('::warning title=イベント取得は一部のみ成功::' + message, flush=True)
    if not blocked and not args.dry_run and not args.recheck_only and selected:
        try:
            report['body_verification'] = 'checking'
            if args.no_rewrite:
                rewrites = [{'summary': f'{e["city"]}の「{e["title"]}」。開催日: {e["date_str"]}。',
                             'description': '開催内容の詳細や変更情報は出典をご確認ください。'} for e, _ in selected]
            else:
                rewrites = ai_rewriter.rewrite_collected_events([e for e, _ in selected])
            report['body_verification'] = 'deterministic_only' if args.no_rewrite else 'deterministic_and_gemini'
            with sqlite3.connect(db_path) as conn:
                save_events(conn, selected, rewrites)
            report['saved'] = len(selected)
        except Exception as exc:
            LOG.error('Import failed: %s', exc)
            blocked = True
            report['status'] = 'failed'
            report['error'] = str(exc)
            if report['body_verification'] == 'checking':
                report['body_verification'] = 'failed'
            if isinstance(exc, BodyVerificationError):
                report['body_verification'] = 'needs_review'
                report['body_issues'] = exc.failures
    if not blocked and not args.dry_run:
        with sqlite3.connect(db_path) as conn:
            save_rechecks(conn, checks)
    review_count = sum(item['status'] != 'matched' for item in checks)
    if review_count:
        LOG.warning('掲載済みイベントの再確認: %d件は要確認・確認不能・未実施。自動削除は行いません', review_count)
        if os.environ.get('GITHUB_ACTIONS') == 'true':
            print(f'::warning title=掲載済みイベントの再確認::{review_count}件をレポートで確認してください。自動削除はしていません。', flush=True)
    if args.output:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    LOG.info('Collection summary: eligible=%d pending=%d selected=%d saved=%d dry_run=%s',
             len(events), len(pending), len(selected), report['saved'], args.dry_run)
    summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary_path:
        lines = ['## イベント収集結果', '', f'結果: **{report["status"]}**', '',
                 '| 収集先 | 解析件数 | 掲載候補 | 結果 |', '| --- | ---: | ---: | --- |']
        for result in reports:
            lines.append(f'| {result["source"]} | {result.get("parsed", "—")} | '
                         f'{result.get("eligible", "—")} | {"取得失敗" if "error" in result else "取得成功"} |')
        lines += ['', f'保存件数: {report["saved"]} / 処理対象: {len(selected)}',
                  '再確認専用：掲載済みイベントの本文・基本情報は変更していません。' if args.recheck_only else '',
                  'dry-runのため保存していません。' if args.dry_run else '',
                  '失敗した収集先の既存データは削除していません。' if failures else '', '']
        lines += ['### 本文の事実確認', '', f'結果: {report["body_verification"]}', '',
                  '### 掲載済みイベントの再確認', '',
                  '日時・会場・料金等の照合であり、本文の全記述を保証する判定ではありません。', '',
                  '| 判定 | 件数 |', '| --- | ---: |']
        for status, count in check_counts.items():
            lines.append(f'| {STATUS_LABELS[status]} | {count} |')
        lines += ['', f'出典変更等による更新保留: {len(held)}件', '', '| ID | イベント | 確認内容（先頭20件） |', '| --- | --- | --- |']
        for item in [item for item in checks if item['status'] != 'matched'][:20]:
            title = item['title'].replace('|', '／').replace('\n', ' ')
            issues = ' / '.join(item['issues']).replace('|', '／').replace('\n', ' ')
            lines.append(f'| {item["event_id"]} | {title} | {issues} |')
        lines += ['', '全件の根拠・変更内容はcollection-report.jsonを参照してください。', '']
        with open(summary_path, 'a', encoding='utf-8') as summary:
            summary.write('\n'.join(lines))
    return 1 if blocked else 0


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    raise SystemExit(main())
