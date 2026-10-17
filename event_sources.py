"""Collect factual event fields. Never copy tourism-site prose or images."""

import csv
import datetime as dt
import io
import logging
import math
import re
import time
import unicodedata
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

LOG = logging.getLogger(__name__)
USER_AGENT = 'ShizuokaEventNaviBot/1.0 (+https://github.com/junkyasan-hub/shizuoka-event-navi)'


@dataclass(frozen=True)
class Source:
    name: str
    city: str
    url: str
    detail_pattern: str = ''


SOURCES = (
    Source('浜松市オープンデータ', '浜松市',
           'https://static.hamamatsu.odpf.net/opendata/v01/221309_hamamatsu_event/221309_hamamatsu_event.csv'),
    Source('静岡市観光ナビ', '静岡市', 'https://www.visit-shizuoka.com/event/index.html',
           r'/event/detail_\d+\.html$'),
    Source('沼津観光ポータル', '沼津市', 'https://numazukanko.jp/event', r'/event/\d+/?$'),
    Source('伊豆・伊東観光ガイド', '伊東市', 'https://itospa.com/event/index.html',
           r'/event/detail_\d+\.html$'),
    Source('伊豆下田観光ガイド', '下田市', 'https://www.shimoda-city.info/event'),
)


def clean(value):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', value or '')).strip()


def date_bounds(value):
    """Accept explicit years; never infer a year for old annual listings."""
    text = clean(value)
    # Time-only, seasonal, and annual schedules without a year need manual review.
    first = re.search(r'(20\d{2})\s*[年/.-]\s*(\d{1,2})\s*[月/.-]\s*(\d{1,2})\s*日?', text)
    if not first:
        return None
    try:
        start = dt.date(*map(int, first.groups()))
        tail = text[first.end():]
        end = start
        full = re.search(r'(20\d{2})\s*[年/.-]\s*(\d{1,2})\s*[月/.-]\s*(\d{1,2})\s*日?', tail)
        short = re.search(r'(\d{1,2})\s*[月/]\s*(\d{1,2})\s*日?', tail)
        day = re.search(r'[〜~～・]\s*(\d{1,2})\s*日', tail)
        if full:
            end = dt.date(*map(int, full.groups()))
        elif short:
            month, day_num = map(int, short.groups())
            end = dt.date(start.year + (month < start.month), month, day_num)
        elif day:
            end = dt.date(start.year, start.month, int(day.group(1)))
        if end < start:
            return None
        return start.isoformat(), end.isoformat()
    except ValueError:
        return None


def factual_event(source, url, title, date_text, location='', address='', fee='', parking=''):
    title, date_text = clean(title), clean(date_text)
    if not title or not date_text:
        raise ValueError('event title or date field missing (site structure may have changed)')
    bounds = date_bounds(date_text)
    # Consecutive day lists such as 10月24日・25日 are safe to treat as a range;
    # nonconsecutive/multiple dates require a recurrence-aware importer.
    date_sequence = re.sub(r'\([^)]*\)', '', date_text)
    if bounds and re.search(r'[、,・]', date_sequence):
        start, end = map(dt.date.fromisoformat, bounds)
        if (end - start).days != 1 or len(re.findall(r'[、,・]', date_sequence)) != 1:
            bounds = None
    if re.search(r'毎|予定|中止|特定日|指定日|土日|平日|曜日|休館|休業|除く', date_text):
        bounds = None
    # Normalize straightforward ranges for the existing site's date parser.
    original_date = date_text
    if bounds:
        start, end = map(dt.date.fromisoformat, bounds)
        date_text = f'{start.year}年{start.month}月{start.day}日'
        if start != end:
            date_text += f'〜{end.year}年{end.month}月{end.day}日'
    return {
        'source_name': source.name, 'source_url': url, 'city': source.city,
        'title': title, 'date_str': date_text, 'source_date_str': original_date,
        'location': clean(location) or '会場は出典をご確認ください',
        'address': clean(address), 'fee': clean(fee) or '出典をご確認ください',
        'parking_info': clean(parking) or '出典をご確認ください',
        'start_date': bounds[0] if bounds else '',
        'end_date': bounds[1] if bounds else '',
    }


def parse_detail(source, url, html):
    soup = BeautifulSoup(html, 'html.parser')
    fields = {}
    for row in soup.select('tr'):
        label, value = row.find('th'), row.find('td')
        if label and value:
            fields[clean(label.get_text(' ', strip=True))] = value.get_text(' ', strip=True)
    for label in soup.select('dt'):
        value = label.find_next_sibling()
        if value and value.name == 'dd':
            fields[clean(label.get_text(' ', strip=True))] = value.get_text(' ', strip=True)
    heading = soup.select_one('h1.title') if source.city == '沼津市' else soup.select_one('h2')
    if not heading:
        raise ValueError('event heading missing')

    def get(*keys):
        return next((fields[k] for k in keys if fields.get(k)), '')

    event = factual_event(
        source, url, heading.get_text(' ', strip=True),
        get('イベント開催期間', '開催期間', '開催日'),
        get('イベント会場名', '会場名', '開催場所', 'イベント開催場所'),
        get('住所'), get('料金'), get('駐車場'),
    )
    event['schedule_note'] = clean(get('開催時間'))
    return event


def parse_shimoda(source, html):
    soup = BeautifulSoup(html, 'html.parser')
    events = []
    for parent in soup.select('[data-testid="richTextElement"]'):
        headings = parent.select('h3')
        if not headings:
            continue
        # Wix publishes the event title/date as lines within the same heading.
        for br in parent.select('br'):
            br.replace_with('\n')
        lines = [clean(line) for heading in headings for line in heading.get_text().splitlines() if clean(line)]
        if len(lines) < 2 or not date_bounds(lines[1]):
            continue
        url = source.url + '#' + parent['id']
        events.append(factual_event(source, url, lines[0], lines[1]))
    if not events:
        raise ValueError('no dated event blocks found on Shimoda listing')
    return events


def parse_hamamatsu(source, content):
    reader = csv.DictReader(io.StringIO(content.decode('cp932')))
    required = {'イベント名', '開始日', '終了日', 'カテゴリー', '場所名称'}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError('Hamamatsu CSV columns changed')
    events = []
    for row in reader:
        if row['カテゴリー'].strip() not in {'イベント', 'おんがく', 'スポーツ'}:
            continue
        try:
            start = dt.date.fromisoformat(row['開始日'].strip())
            end = dt.date.fromisoformat(row['終了日'].strip() or start.isoformat())
        except ValueError:
            continue
        text = f'{start.year}年{start.month}月{start.day}日'
        if end != start:
            text += f'〜{end.year}年{end.month}月{end.day}日'
        event = factual_event(source, source.url + '#' + row['NO'], row['イベント名'], text,
                              row['場所名称'], row['住所'],
                              ' '.join(filter(None, (row['料金(基本)'], row['料金(詳細)']))),
                              row['駐車場情報'])
        event['official_url'] = row['URL'].strip() or source.url
        try:
            lat, lng = float(row['緯度']), float(row['経度'])
            if math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180:
                event['lat'], event['lng'] = lat, lng
        except (TypeError, ValueError):
            pass
        # The CSV is CC BY; preserve date/time remarks instead of discarding them.
        event['schedule_note'] = clean(' '.join(row.get(k, '') for k in (
            '開始時間', '終了時間', '開始日時特記事項')))
        events.append(event)
    return events


class Fetcher:
    def __init__(self, interval=2.0):
        self.session = requests.Session()
        self.session.headers['User-Agent'] = USER_AGENT
        self.interval = max(2.0, interval)
        self.last = {}
        self.robots = {}

    def _request(self, url):
        host = urlsplit(url).netloc
        time.sleep(max(0, self.interval - (time.monotonic() - self.last.get(host, 0))))
        self.last[host] = time.monotonic()
        for attempt in range(3):
            response = self.session.get(url, timeout=30)
            if response.status_code not in {429, 500, 502, 503, 504} or attempt == 2:
                return response
            # Bounded retries for transient responses, never retry an access denial.
            time.sleep(2 ** (attempt + 1))
            self.last[host] = time.monotonic()

    def get(self, url):
        parts = urlsplit(url)
        origin = f'{parts.scheme}://{parts.netloc}'
        if origin not in self.robots:
            response = self._request(origin + '/robots.txt')
            # RFC 9309: unavailable robots.txt (4xx, excluding transient 429)
            # supplies no rules. This does not bypass a denial on the data itself.
            if 400 <= response.status_code < 500 and response.status_code != 429:
                rules = 'User-agent: *\nAllow: /'
            else:
                response.raise_for_status()
                rules = response.text
            robot = RobotFileParser()
            robot.parse(rules.splitlines())
            self.robots[origin] = robot
        robot = self.robots[origin]
        if not robot.can_fetch(USER_AGENT, url):
            raise RuntimeError('robots.txt disallows this event URL')
        delay = robot.crawl_delay(USER_AGENT) or robot.crawl_delay('*')
        if delay:
            time.sleep(max(0, delay - (time.monotonic() - self.last.get(parts.netloc, 0))))
        response = self._request(url)
        response.raise_for_status()
        if 'text/html' in response.headers.get('Content-Type', ''):
            # These Japanese sites declare UTF-8; requests otherwise guesses Latin-1.
            response.encoding = 'utf-8'
        return response


def collect(source, fetcher, max_details=30):
    response = fetcher.get(source.url)
    if source.city == '浜松市':
        return parse_hamamatsu(source, response.content)
    if source.city == '下田市':
        return parse_shimoda(source, response.text)
    soup = BeautifulSoup(response.text, 'html.parser')
    urls = []
    for link in soup.select('a[href]'):
        url = urljoin(source.url, link['href'])
        parts = urlsplit(url)
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, '', ''))
        if parts.netloc == urlsplit(source.url).netloc and re.search(source.detail_pattern, parts.path):
            if url not in urls:
                urls.append(url)
    if not urls:
        raise ValueError('no event detail links found (site structure may have changed)')
    events = []
    for url in urls[:max_details]:
        html = fetcher.get(url).text
        try:
            events.append(parse_detail(source, url, html))
        except ValueError as exc:
            LOG.warning('%s: skip %s: %s', source.name, url, exc)
    if not events:
        raise ValueError('no event details could be parsed')
    LOG.info('%s: detail links=%d fetched=%d', source.name, len(urls), len(events))
    return events
