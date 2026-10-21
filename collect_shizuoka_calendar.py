"""Read factual fields from Shizuoka city event tables; no prose/photo copying."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import urljoin,urlsplit,quote
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from event_sources import Fetcher,clean
from publication_gate import FIELDS,fingerprint

ORIGIN='https://www.city.shizuoka.lg.jp'
POLICY=ORIGIN+'/s009072.html'
PATTERN=re.compile(r'^/s\d+/s\d+\.html$')
DATE=re.compile(r'(20\d{2})年(\d{1,2})月(\d{1,2})日')

def valid_url(url):
    parts=urlsplit(url)
    return parts.scheme=='https' and parts.netloc=='www.city.shizuoka.lg.jp' and bool(PATTERN.fullmatch(parts.path)) and not parts.query and not parts.fragment


def detail_record(url,html,today):
    if not valid_url(url):raise ValueError('Not a city event detail URL')
    soup=BeautifulSoup(html,'html.parser')
    headings=soup.find_all('h1')
    if len(headings)!=1:raise ValueError('Ambiguous event heading')
    title=clean(headings[0].get_text(' ',strip=True))
    if not title or any(w in title for w in ('中止','延期','公開終了')):raise ValueError('Cancelled or non-event page')
    values={}
    for tr in soup.select('tr'):
        cells=tr.find_all(['th','td'],recursive=False)
        if len(cells)!=2:continue
        label=clean(cells[0].get_text(' ',strip=True))
        if label not in ('年月日','時間','備考','開催場所'):continue
        text=clean(cells[1].get_text(' ',strip=True))
        if label in values and values[label]!=text:raise ValueError('Conflicting table fields')
        if label=='年月日' and len(cells[1].find_all('li'))>1:raise ValueError('Multiple date occurrences need review')
        values[label]=text
    schedule=values.get('年月日',''); dates=DATE.findall(schedule)
    if len(dates) not in (1,2):raise ValueError('Explicit event dates missing or ambiguous')
    if len(dates)==2 and not re.search(r'から|〜|～',schedule):raise ValueError('Separate dates are not a continuous range')
    if any(w in schedule for w in ('予定','未定','毎','除く','中止','延期','、')):raise ValueError('Ambiguous schedule')
    start=dt.date(*map(int,dates[0]));end=dt.date(*map(int,dates[-1]))
    if end<start or end<today:raise ValueError('Invalid or expired dates')
    venue=values.get('開催場所','')
    if not venue or any(w in venue for w in ('未定','調整中')):raise ValueError('Venue unconfirmed')
    notes=values.get('備考','');times=values.get('時間','')
    if any(w in notes+times for w in ('開催中止','開催延期')):raise ValueError('Cancellation notice')
    # Non-contiguous opening days are kept explicit, never promised as daily opening.
    date_str=f'{start.year}年{start.month}月{start.day}日'
    if end!=start:date_str+=f'〜{end.year}年{end.month}月{end.day}日'
    date_str+=' '+times
    if notes:date_str+='／'+notes
    row=dict.fromkeys(FIELDS,'')
    row.update(item_type='event',title=title,date_str=date_str.strip(),city='静岡市',location=venue,
               lat=0.0,lng=0.0,official_url=url,google_maps_url='https://maps.google.com/?q='+quote('静岡市 '+venue),
               tags='市公式カレンダー',summary=title,fee='料金・参加条件は公式ページをご確認ください',
               parking_info='駐車場の利用条件は公式ページをご確認ください',
               organizer='主催・問い合わせ先は公式ページをご確認ください',target_age='公式ページをご確認ください',
               is_free_parking=0,is_stroller_ok=0,is_rainy_ok=0,
               description=f'開催期間：{schedule}\n時間：{times or "公式ページをご確認ください"}\n会場：{venue}\n注意事項：{notes or "公式ページをご確認ください"}\n\n出典：静岡市公式イベント情報\n{url}\n本文・画像は転載していません。最新の料金・申込条件・開催状況は出典をご確認ください。')
    return row


def calendar_links(html):
    soup=BeautifulSoup(html,'html.parser')
    # Only links inside calendar tables: exclude global navigation and recommendations.
    urls=[]
    for link in soup.select('table a[href]'):
        url=urljoin(ORIGIN,link['href'])
        if valid_url(url) and url not in urls:urls.append(url)
    if not urls:raise ValueError('No supported calendar links; structure may have changed')
    return urls


def collect(fetcher,today,max_details=20):
    urls=[]
    for offset in (0,1):
        month=today.month+offset;year=today.year+(month>12);month=(month-1)%12+1
        listing=f'{ORIGIN}/cgi-bin/event_cal_multi/calendar.cgi?year={year}&month={month}&type=2'
        response=fetcher.get(listing)
        if urlsplit(response.url).netloc!='www.city.shizuoka.lg.jp':raise ValueError('Unexpected calendar redirect')
        for url in calendar_links(response.text):
            if url not in urls:urls.append(url)
    rows=[];held=[]
    for url in urls[:max_details]:
        try:
            response=fetcher.get(url)
            if response.url!=url:raise ValueError('Detail redirected; no longer authoritative at this URL')
            row=detail_record(url,response.text,today)
            rows.append((url,row,hashlib.sha256(response.content).hexdigest()))
        except Exception as exc:held.append({'url':url,'reason':str(exc)})
    return rows,held,urls[:max_details]


def save(conn,rows,checked_urls,now):
    from manual_events import controls
    conn.row_factory=sqlite3.Row
    protected=controls(conn);saved=[]
    with conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS city_calendar_publication (
            source_url TEXT PRIMARY KEY,event_id INTEGER NOT NULL,record_hash TEXT NOT NULL,
            fetched_at TEXT NOT NULL,document_hash TEXT NOT NULL)''')
        for url in checked_urls:conn.execute('DELETE FROM city_calendar_publication WHERE source_url=?',(url,))
        for url,row,digest in rows:
            existing=conn.execute('SELECT * FROM events WHERE official_url=? ORDER BY id LIMIT 1',(url,)).fetchone()
            ident=existing['id'] if existing else None
            # Preserve manual controls even if an older record used another source URL.
            matches=conn.execute('SELECT id FROM events WHERE title=? AND city=?',(row['title'],'静岡市')).fetchall()
            if ident in protected or any(r['id'] in protected for r in matches):continue
            vals=[row[k] for k in FIELDS]
            if ident is None:
                ident=conn.execute('INSERT INTO events ('+','.join(FIELDS)+') VALUES ('+','.join('?' for _ in FIELDS)+')',vals).lastrowid
            else:conn.execute('UPDATE events SET '+','.join(k+'=?' for k in FIELDS)+' WHERE id=?',vals+[ident])
            conn.execute('INSERT INTO city_calendar_publication VALUES (?,?,?,?,?)',(url,ident,fingerprint(row),now.isoformat(),digest))
            saved.append(ident)
    return saved


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',default='events.db');parser.add_argument('--backup',required=True)
    parser.add_argument('--report',required=True);parser.add_argument('--max-details',type=int,default=20)
    args=parser.parse_args()
    if args.max_details<1 or not Path(args.db).is_file() or Path(args.backup).exists():parser.error('Invalid limit, database or backup path')
    report={'source':ORIGIN,'saved':0}
    try:
        now=dt.datetime.now(dt.timezone.utc)
        rows,held,checked=collect(Fetcher(),now.astimezone(ZoneInfo('Asia/Tokyo')).date(),args.max_details)
        with sqlite3.connect(args.db) as conn:
            Path(args.backup).parent.mkdir(parents=True,exist_ok=True)
            with sqlite3.connect(args.backup) as backup:conn.backup(backup)
            ids=save(conn,rows,checked,now)
        report.update(status='completed',saved=len(ids),held=held,checked=len(checked),fetched_at=now.isoformat())
    except Exception as exc:
        report.update(status='failed',error=str(exc));raise
    finally:Path(args.report).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
