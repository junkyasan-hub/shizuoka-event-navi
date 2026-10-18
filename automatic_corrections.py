"""Plan corrections only for unambiguous official detail records in the same year."""
import collections
import sqlite3
from event_sources import date_bounds, factual_event
from event_verification import RECHECK_SOURCES, is_detail_url, normalize, source_has_cancel_notice
from manual_events import controls


def plan_corrections(conn, checks, observed):
    conn.row_factory = sqlite3.Row
    rows = {r['id']: dict(r) for r in conn.execute("SELECT * FROM events WHERE item_type='event'")}
    protected = controls(conn)
    counts = collections.Counter((r['city'], normalize(r['title'])) for r in rows.values())
    observed_by_url = collections.defaultdict(list)
    for event in observed:
        observed_by_url[event['source_url']].append(event)
    owners = {}
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='event_imports'").fetchone():
        owners = dict(conn.execute('SELECT source_key,event_id FROM event_imports'))
    candidates, decisions = [], []
    for check in checks:
        if check['status'] != 'changed':
            continue
        event_id = check['event_id'];row = rows.get(event_id)
        facts = check.get('source_facts', {})
        url = check.get('source_url', '')
        reason = None
        source = next((s for s in RECHECK_SOURCES if s.city == facts.get('city') and is_detail_url(s,url)), None)
        old_dates, new_dates = date_bounds(row['date_str']) if row else None, date_bounds(facts.get('date_str',''))
        if not row or event_id in protected:
            reason = '手動編集・非掲載で保護されているため自動訂正しません'
        elif not source or source.city == '下田市':
            reason = '公式の個別詳細ページで確認できないため保留'
        elif normalize(row['title']) != normalize(facts.get('title','')) or row['city'] != facts.get('city'):
            reason = '名称・地域が一致せず同一イベントを確定できないため保留'
        elif not old_dates or not new_dates or old_dates[0][:4] != new_dates[0][:4]:
            reason = '開催年が一致しない、または開催日を確定できないため保留'
        elif source_has_cancel_notice(facts):
            reason = '中止情報は人による確認が必要'
        elif owners.get(url,event_id) != event_id:
            reason = '出典が別の掲載済みイベントと結び付いているため保留'
        elif counts[(row['city'],normalize(row['title']))] != 1:
            reason = '同名の掲載済みイベントが複数あり開催回を特定できないため保留'
        elif not check.get('differences') and not check.get('source_changed_fields'):
            reason = '本文だけの問題は自動訂正せず確認を依頼'
        if reason:
            decisions.append({'event_id':event_id,'title':check['title'],'reason':reason})
            continue
        found = observed_by_url.get(url,[])
        if len(found)>1:
            decisions.append({'event_id':event_id,'title':check['title'],'reason':'同じ出典に複数候補があるため保留'})
            continue
        event = dict(found[0]) if found else factual_event(source,url,facts['title'],
                    facts.get('source_date_str', facts['date_str']), facts.get('location',''),
                    facts.get('address',''), facts.get('fee',''), facts.get('parking_info',''))
        if not found:
            event.update({k:v for k,v in facts.items() if k != 'date_str'})
        # A fresh parse must provide definite dates; do not infer annual/recurring schedules.
        if not event.get('start_date') or not event.get('end_date') or (event['start_date'],event['end_date']) != new_dates:
            decisions.append({'event_id':event_id,'title':check['title'],'reason':'詳細ページの開催日を確定できないため保留'})
            continue
        event['_auto_correction'] = {'before':row,'source_url':url,'source_facts':facts,
                                     'differences':check.get('differences',[]),
                                     'source_changes':check.get('source_changes',{})}
        candidates.append((event,event_id))
    # Never use one detail page to update multiple records.
    urls = collections.Counter(e['source_url'] for e,_ in candidates)
    safe = [(e,i) for e,i in candidates if urls[e['source_url']]==1]
    for e,i in candidates:
        if urls[e['source_url']] > 1:
            decisions.append({'event_id':i,'title':e['title'],'reason':'出典が複数レコードに一致するため保留'})
    return safe, decisions
