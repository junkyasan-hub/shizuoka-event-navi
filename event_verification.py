"""Evidence-based checks. Unknown or unavailable evidence is never a deletion."""

import collections
import datetime as dt
import json
import re
import sqlite3
import unicodedata
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from event_sources import SOURCES, Source, clean, date_bounds, parse_detail, parse_shimoda

FACT_FIELDS = ('title', 'city', 'date_str', 'source_date_str', 'schedule_note',
               'location', 'address', 'fee', 'parking_info', 'source_name', 'source_notes')
BODY_CHECK_SCOPE = 'dates, times, yen amounts, and explicit free/rain/parking claims'
STATUS_LABELS = {'matched': '基本情報の照合一致', 'changed': '変更・矛盾の確認が必要',
                 'cancelled': '出典に中止表記（確認が必要）', 'unavailable': '通信・解析で確認不能',
                 'needs_review': '根拠不足・手動確認が必要', 'not_checked': '取得上限のため未実施'}
RECHECK_SOURCES = SOURCES + (
    # Recheck existing precise URLs only; this is not a new collection source.
    Source('熱海市観光協会（掲載済み情報の再確認）', '熱海市',
           'https://www.ataminews.gr.jp/event', r'/event/\d+/?$'),
)


def factual_payload(event):
    return {key: str(event.get(key, '')) for key in FACT_FIELDS}


def claims(text):
    text = clean(text)
    dates = set()
    for year, month, day in re.findall(r'(20\d{2})[年/.-](\d{1,2})[月/.-](\d{1,2})日?', text):
        dates.add(f'{int(year):04d}-{int(month):02d}-{int(day):02d}')
    month_days = {f'{int(m):02d}-{int(d):02d}' for m, d in re.findall(r'(\d{1,2})月(\d{1,2})日', text)}
    # Match slash dates only without treating HH:MM as a date.
    month_days.update(f'{int(m):02d}-{int(d):02d}' for m, d in re.findall(
        r'(?<![\d/:])(\d{1,2})/(\d{1,2})(?![\d/:])', text)
                     if 1 <= int(m) <= 12 and 1 <= int(d) <= 31)
    times = {f'{int(h):02d}:{int(m):02d}' for h, m in re.findall(r'(\d{1,2}):(\d{2})', text)}
    for period, hour, minute in re.findall(r'(午前|午後)?(\d{1,2})時(?!間)(?:(\d{1,2})分)?', text):
        hour = int(hour)
        if period == '午後' and hour < 12:
            hour += 12
        if period == '午前' and hour == 12:
            hour = 0
        times.add(f'{hour:02d}:{int(minute or 0):02d}')
    amounts = set()
    for value, unit in re.findall(r'([\d,]+(?:\.\d+)?)\s*(万)?円', text):
        amounts.add(int(float(value.replace(',', '')) * (10000 if unit else 1)))
    return {'dates': dates, 'month_days': month_days, 'times': times, 'amounts': amounts}


def check_body(event, rewrite):
    """Detect concrete unsupported claims, without declaring all prose verified."""
    facts = factual_payload(event)
    schedule = ' '.join(facts[key] for key in ('date_str', 'source_date_str', 'schedule_note', 'source_notes'))
    evidence = claims(schedule)
    bounds = date_bounds(event.get('date_str', ''))
    if bounds:
        for date in bounds:
            evidence['dates'].add(date)
            evidence['month_days'].add(date[5:])
    for date in evidence['dates']:
        evidence['month_days'].add(date[5:])
    # Parking costs and program-specific fees are legitimate amounts too.
    # Do not use unrelated numbers from addresses/URLs as evidence.
    evidence['amounts'] = claims(' '.join(facts[key] for key in ('fee', 'parking_info', 'source_notes')))['amounts']
    text = clean(rewrite.get('summary', '') + '\n' + rewrite.get('description', ''))
    stated = claims(text)
    issues = []
    for kind, label in (('dates', '開催日'), ('month_days', '月日'), ('times', '時刻'), ('amounts', '料金')):
        for value in sorted(stated[kind] - evidence[kind]):
            issues.append(f'出典の該当項目にない{label}: {value}')
    for year, month, day, weekday in re.findall(
            r'(?:(20\d{2})年)?(\d{1,2})月(\d{1,2})日\s*\(([月火水木金土日])', text):
        if year:
            event_year = int(year)
        else:
            # A December application deadline may precede a January event.
            # Do not invent its year from the event's start date.
            dates = {value for value in evidence['dates'] if value.endswith(f'-{int(month):02d}-{int(day):02d}')}
            if len(dates) != 1:
                continue
            event_year = int(next(iter(dates))[:4])
        try:
            actual_weekday = '月火水木金土日'[dt.date(event_year, int(month), int(day)).weekday()]
            if actual_weekday != weekday:
                issues.append(f'曜日が暦と異なる: {event_year}年{month}月{day}日({weekday})')
        except ValueError:
            issues.append(f'存在しない日付: {event_year}年{month}月{day}日')
    # Context matters: admission being free does not prove free parking.
    if re.search(r'駐車(?:場|料金)?(?:は|が|も|代は|料金は)?無料|無料駐車', text):
        if '無料' not in facts['parking_info'] or re.search(r'無料.*(?:なし|ございません)', facts['parking_info']):
            issues.append('無料駐車場の根拠がない')
    if re.search(r'(?:入場|入園|入館|参加|観覧)(?:料|料金)?(?:は|が|も)?無料', text):
        if '無料' not in facts['fee'] and evidence['amounts'] != {0}:
            issues.append('入場・参加無料の根拠がない')
    if '雨天決行' in text and '雨天決行' not in ' '.join(facts.values()):
        issues.append('雨天決行の根拠がない')
    if re.search(r'<[^>]+>|javascript:', text, re.I):
        issues.append('紹介文にHTMLまたはスクリプト表現がある')
    return {'status': 'needs_review' if issues else 'passed', 'issues': list(dict.fromkeys(issues)), 'scope': BODY_CHECK_SCOPE}


def require_supported_bodies(events, rewrites):
    if len(events) != len(rewrites):
        raise ValueError('body check count mismatch')
    failures = []
    for index, (event, rewrite) in enumerate(zip(events, rewrites)):
        result = check_body(event, rewrite)
        if result['issues']:
            failures.append({'index': index, 'title': event['title'], **result})
    if failures:
        raise BodyVerificationError(failures)


class BodyVerificationError(RuntimeError):
    def __init__(self, failures):
        self.failures = failures
        super().__init__('本文の事実確認に失敗。新規掲載・更新を保留: ' +
                         '; '.join(f'{item["title"]}: {", ".join(item["issues"])}' for item in failures))


def normalize(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', value or '')).casefold()


def event_identity_title(value):
    value = clean(value)
    value = re.sub(r'^[\[【(](?:開催)?中止[\]】)]\s*', '', value)
    return normalize(value)


def source_has_cancel_notice(event):
    # Conditional "雨天中止" is not an announcement that the event was cancelled.
    title = clean(event['title'])
    return bool(re.search(r'^[\[【(]?\s*(?:開催)?中止|[\[【(](?:開催)?中止[\]】)]|開催中止のお知らせ', title))


def is_detail_url(source, url):
    parts, base = urlsplit(url), urlsplit(source.url)
    if parts.scheme != 'https' or parts.netloc != base.netloc:
        return False
    if source.city == '下田市':
        return parts.path == '/event' and bool(parts.fragment)
    return bool(source.detail_pattern and re.search(source.detail_pattern, parts.path))


def recheck_published(conn, observed, successful_sources, fetcher, max_extra=20):
    """Compare fresh facts with published records. Never edit events here."""
    conn.row_factory = sqlite3.Row
    records = [dict(row) for row in conn.execute("SELECT * FROM events WHERE item_type='event' ORDER BY id")]
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    imported = {}
    if 'event_imports' in tables:
        imported = {row[0]: row[1] for row in conn.execute('SELECT event_id,source_key FROM event_imports')}
    previous = {}
    if 'event_rechecks' in tables:
        previous = {row['event_id']: json.loads(row['evidence_json'])
                    for row in conn.execute('SELECT * FROM event_rechecks')}
    by_key = {event['source_url']: event for event in observed}
    by_name = collections.defaultdict(list)
    for event in observed:
        by_name[(event['city'], event_identity_title(event['title']))].append(event)
    extra_count = 0
    extra_cache = {}
    page_cache = {}
    results = []
    today = dt.datetime.now(ZoneInfo('Asia/Tokyo')).date().isoformat()
    # Prefer upcoming records if the extra-request budget is exhausted.
    records.sort(key=lambda row: (bool(date_bounds(row['date_str']) and date_bounds(row['date_str'])[1] < today), row['id']))
    for row in records:
        source = next((source for source in RECHECK_SOURCES if source.city == row['city']), None)
        result = {'event_id': row['id'], 'title': row['title'], 'status': 'needs_review',
                  'source_url': imported.get(row['id'], row.get('official_url', '')), 'issues': [],
                  'published_facts': {field: row.get(field, '') for field in ('title', 'date_str', 'location', 'fee')},
                  'differences': [],
                  'scope': 'source title/date/venue, source changes, and limited body claim checks'}
        key = imported.get(row['id'])
        actual = by_key.get(key) if key else None
        if actual is None:
            candidates = by_name[(row['city'], event_identity_title(row['title']))]
            exact_dates = [event for event in candidates if
                           (event['start_date'], event['end_date']) == date_bounds(row['date_str'])]
            if exact_dates and len({normalize(e['location']) for e in exact_dates}) == 1:
                actual = exact_dates[0]
            elif len(candidates) == 1:
                actual = candidates[0]
        if source in SOURCES and source.name not in successful_sources:
            result['status'] = 'unavailable'
            result['issues'].append('収集元の通信・解析に失敗。不存在とは判断しない')
        elif actual is None and source and is_detail_url(source, result['source_url']):
            url = result['source_url']
            try:
                if url not in extra_cache:
                    page_url = url.split('#')[0]
                    if page_url not in page_cache:
                        if extra_count >= max_extra:
                            result['status'] = 'not_checked'
                            result['issues'].append('追加取得の上限に到達。今回の再確認は未実施')
                            results.append(result)
                            continue
                        extra_count += 1
                        page_cache[page_url] = fetcher.get(page_url).text
                    html = page_cache[page_url]
                    if source.city == '下田市':
                        extra_cache[url] = next((e for e in parse_shimoda(source, html) if e['source_url'] == url), None)
                    else:
                        extra_cache[url] = parse_detail(source, url, html)
                actual = extra_cache[url]
            except Exception as exc:
                result['status'] = 'unavailable'
                result['issues'].append('詳細ページを再確認できない: ' + type(exc).__name__)
        if result['status'] != 'unavailable' and actual:
            result['source_url'] = actual['source_url']
            result['source_facts'] = factual_payload(actual)
            issues = result['issues']
            if source_has_cancel_notice(actual):
                result['status'] = 'cancelled'
                issues.append('出典のイベント名に中止の告知あり。自動削除せず確認を依頼')
            else:
                if normalize(row['title']) != normalize(actual['title']):
                    issues.append('出典とイベント名が異なる')
                    result['differences'].append({'field': 'title', 'published': row['title'], 'source': actual['title']})
                if not actual['start_date'] or not actual['end_date']:
                    issues.append('出典の開催日を確定できない')
                elif date_bounds(row['date_str']) != (actual['start_date'], actual['end_date']):
                    issues.append('出典と開催日が異なる')
                    result['differences'].append({'field': 'date_str', 'published': row['date_str'], 'source': actual['source_date_str']})
                venue = actual.get('location', '')
                if venue and '出典をご確認' not in venue and normalize(row['location']) != normalize(venue):
                    issues.append('出典と会場が異なる')
                    result['differences'].append({'field': 'location', 'published': row['location'], 'source': venue})
                stored = previous.get(row['id'], {})
                previous_facts = stored.get('source_facts') or stored.get('last_confirmed_source_facts')
                if previous_facts:
                    changed = [field for field in FACT_FIELDS if field in previous_facts and
                               previous_facts.get(field, '') != result['source_facts'].get(field, '')]
                    if changed:
                        result['source_changed_fields'] = changed
                        result['source_changes'] = {field: {'previous': previous_facts.get(field, ''),
                                                           'current': result['source_facts'].get(field, '')} for field in changed}
                        issues.append('前回確認時から出典の情報が変化: ' + ', '.join(changed))
                old_amounts, new_amounts = claims(row.get('fee', ''))['amounts'], claims(actual.get('fee', ''))['amounts']
                if old_amounts and new_amounts and not old_amounts.issubset(new_amounts):
                    issues.append('掲載された料金と出典の金額が異なる')
                    result['differences'].append({'field': 'fee', 'published': row['fee'], 'source': actual['fee']})
                if '無料' in row.get('fee', '') and '無料' not in actual.get('fee', '') and new_amounts - {0}:
                    issues.append('掲載では無料だが、出典には有料の記載がある')
                # Do not audit the appended source citation/license as AI prose.
                body = row.get('description', '').split('\n\n開催日:')[0].split('\n\n出典:')[0]
                body_result = check_body(actual, {'summary': row.get('summary', ''), 'description': body})
                result['body_check'] = body_result
                issues.extend(body_result['issues'])
                result['status'] = 'changed' if issues else 'matched'
        elif result['status'] != 'unavailable':
            result['issues'].append('同一の開催を裏付ける詳細情報が不足。未掲載・削除とは断定しない')
        if 'source_facts' not in result:
            stored = previous.get(row['id'], {})
            baseline = stored.get('source_facts') or stored.get('last_confirmed_source_facts')
            if baseline:
                result['last_confirmed_source_facts'] = baseline
        results.append(result)
    return results


def save_rechecks(conn, results):
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()
    with conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS event_rechecks (
            event_id INTEGER PRIMARY KEY, checked_at TEXT NOT NULL,
            status TEXT NOT NULL, evidence_json TEXT NOT NULL)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS event_recheck_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL,
            checked_at TEXT NOT NULL, status TEXT NOT NULL, evidence_json TEXT NOT NULL)''')
        for result in results:
            encoded = json.dumps(result, ensure_ascii=False, sort_keys=True)
            old = conn.execute('SELECT evidence_json FROM event_rechecks WHERE event_id=?', (result['event_id'],)).fetchone()
            if old is None or old[0] != encoded:
                conn.execute('INSERT INTO event_recheck_history (event_id,checked_at,status,evidence_json) VALUES (?,?,?,?)',
                             (result['event_id'], stamp, result['status'], encoded))
            conn.execute('''INSERT INTO event_rechecks VALUES (?,?,?,?) ON CONFLICT(event_id)
                DO UPDATE SET checked_at=excluded.checked_at,status=excluded.status,evidence_json=excluded.evidence_json''',
                         (result['event_id'], stamp, result['status'], encoded))
