import sqlite3
import os
import datetime
import json
from jinja2 import Environment, FileSystemLoader

DB_PATH = "events.db"
TEMPLATES_DIR = "templates"
OUTPUT_DIR = "dist"
EVENTS_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "events")

CITY_OFFICIAL_MAP = {
    "静岡市": "https://www.visit-shizuoka.com/",
    "浜松市": "https://www.hamamatsu-navi.jp/",
    "沼津市": "https://numazukanko.jp/",
    "熱海市": "https://www.ataminews.gr.jp/",
    "伊東市": "https://itospa.com/",
    "富士市": "https://www.fujikawarakuza.co.jp/",
    "富士宮市": "https://fujinomiya.gr.jp/",
    "御殿場市": "https://gotembakanko.jp/",
    "焼津市": "https://www.yaizu.gr.jp/",
    "掛川市": "https://www.kakegawa-kankou.com/",
    "磐田市": "https://kankou-iwata.jp/",
    "三島市": "https://www.mishima-kankou.com/",
    "藤枝市": "https://www.fujieda-kanko.jp/",
    "伊豆市": "https://www.izushikankou.com/",
    "袋井市": "https://fukuroi-kankou.jp/",
    "下田市": "https://www.shimoda-city.info/",
    "島田市": "https://www.shimada-ta.jp/",
    "裾野市": "https://www.city.susono.shizuoka.jp/"
}

import re

def parse_event_dates(date_str, item_type='event'):
    if item_type in ('spot', 'gourmet') or '通年' in date_str or '常設' in date_str:
        return '1970-01-01', '2099-12-31'
    dates = re.findall(r'(\d{4})年(\d{1,2})月(\d{1,2})日', date_str)
    if dates:
        sy, sm, sd = dates[0]
        s_iso = f'{sy}-{int(sm):02d}-{int(sd):02d}'
        if len(dates) > 1:
            ey, em, ed = dates[1]
            e_iso = f'{ey}-{int(em):02d}-{int(ed):02d}'
        else:
            m_end = re.search(r'〜\s*(\d{1,2})月(\d{1,2})日', date_str)
            if m_end:
                em, ed = m_end.groups()
                e_iso = f'{sy}-{int(em):02d}-{int(ed):02d}'
            else:
                e_iso = s_iso
        return s_iso, e_iso
    return '1970-01-01', '2099-12-31'

def parse_event_status(date_str):
    if "通年" in date_str or "常設" in date_str:
        return False, "営業中"
    
    if "2026年4月" in date_str or "2026年5月" in date_str or "2026年8月" in date_str:
        return True, "終了"
    
    return False, "開催予定"

def enrich_item(item):
    item = dict(item)
    is_ended, status_label = parse_event_status(item["date_str"])
    item["is_ended"] = is_ended
    item["status_label"] = status_label
    
    start_iso, end_iso = parse_event_dates(item["date_str"], item.get("item_type", "event"))
    item["start_iso"] = start_iso
    item["end_iso"] = end_iso
    
    if not item.get("official_url") or "example.com" in item.get("official_url", ""):
        item["official_url"] = CITY_OFFICIAL_MAP.get(item["city"], "https://www.pref.shizuoka.jp/")

    schema_type = "Event"
    if item.get("item_type") == "spot":
        schema_type = "TouristAttraction"
    elif item.get("item_type") == "gourmet":
        schema_type = "Restaurant"

    json_ld = {
        "@context": "https://schema.org",
        "@type": schema_type,
        "name": item["title"],
        "description": item["summary"],
        "image": [item["image_url"]],
        "url": item["official_url"],
        "location": {
            "@type": "Place",
            "name": item["location"],
            "address": {
                "@type": "PostalAddress",
                "addressLocality": item["city"],
                "streetAddress": item.get("address", item["location"]),
                "addressCountry": "JP"
            },
            "geo": {
                "@type": "GeoCoordinates",
                "latitude": item.get("lat", 34.9769),
                "longitude": item.get("lng", 138.3831)
            }
        }
    }

    if schema_type == "Event":
        json_ld["eventAttendanceMode"] = "https://schema.org/OfflineEventAttendanceMode"
        json_ld["eventStatus"] = "https://schema.org/EventCancelled" if is_ended else "https://schema.org/EventScheduled"
        json_ld["organizer"] = {
            "@type": "Organization",
            "name": item["organizer"]
        }

    item["json_ld"] = json.dumps(json_ld, ensure_ascii=False, indent=2)
    return item

def extract_calendar_events(items):
    calendar_events = []
    for item in items:
        start_iso = None
        end_iso = None
        date_str = item["date_str"]

        if "2026年9月12日" in date_str:
            start_iso = "2026-09-12"
            if "9月13日" in date_str:
                end_iso = "2026-09-14"
        elif "2026年9月13日" in date_str:
            start_iso = "2026-09-13"
        elif "2026年4月3日" in date_str:
            start_iso = "2026-04-03"
            end_iso = "2026-04-06"
        elif "2026年4月19日" in date_str:
            start_iso = "2026-04-19"
        elif "2026年5月3日" in date_str:
            start_iso = "2026-05-03"
            end_iso = "2026-05-06"

        if start_iso:
            color = "#0284c7"
            if item.get("item_type") == "spot":
                color = "#059669"
            elif item.get("item_type") == "gourmet":
                color = "#d97706"
            if item.get("is_ended"):
                color = "#64748b"

            cal_evt = {
                "id": str(item["id"]),
                "title": ("🔒 " if item.get("is_ended") else "") + item["title"],
                "start": start_iso,
                "backgroundColor": color,
                "borderColor": color,
                "extendedProps": {
                    "itemId": item["id"],
                    "title": item["title"],
                    "location": item["location"],
                    "address": item.get("address", ""),
                    "fee": item["fee"],
                    "organizer": item["organizer"],
                    "parking": item["parking_info"],
                    "summary": item["summary"],
                    "lat": item.get("lat", 34.9769),
                    "lng": item.get("lng", 138.3831),
                    "isEnded": item.get("is_ended", False),
                    "officialUrl": item.get("official_url", "")
                }
            }
            if end_iso:
                cal_evt["end"] = end_iso
            calendar_events.append(cal_evt)

    return json.dumps(calendar_events, ensure_ascii=False)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def fetch_events():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events")
    rows = cursor.fetchall()
    conn.close()

    items = [enrich_item(row) for row in rows]
    items.sort(key=lambda x: (x["is_ended"], x["id"]))
    return items

def generate_site():
    print("[START] Starting static site generation with Calendar & SEO...")

    os.makedirs(EVENTS_OUTPUT_DIR, exist_ok=True)

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
    index_template = env.get_template("index.html")
    detail_template = env.get_template("detail.html")

    events = fetch_events()
    calendar_events_json = extract_calendar_events(events)

    all_tags_set = set()
    cities_set = set()
    for event in events:
        tags_list = [t.strip() for t in event["tags"].split(",") if t.strip()]
        all_tags_set.update(tags_list)
        if event.get("city"):
            cities_set.add(event["city"].strip())

    all_tags = sorted(list(all_tags_set))
    cities = sorted(list(cities_set))

    # 注目ピックアップイベントの抽出 (主要イベントまたはおすすめ4件)
    featured_keywords = ["大道芸", "熱海海上花火", "修善寺温泉", "焼津", "三嶋大社", "日本平", "三保松原", "さわやか"]
    featured_events = [e for e in events if any(k in e["title"] for k in featured_keywords) and not e.get("is_ended")]
    if len(featured_events) < 4:
        featured_events = [e for e in events if not e.get("is_ended")][:4]
    featured_events = featured_events[:4]

    current_year = datetime.datetime.now().year

    # Render index.html
    index_html = index_template.render(
        events=events,
        featured_events=featured_events,
        calendar_events_json=calendar_events_json,
        all_tags=all_tags,
        cities=cities,
        current_year=current_year,
        base_url=""
    )
    index_path = os.path.join(OUTPUT_DIR, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)
    print(f"[OK] Generated: {index_path}")

    # Render detail pages
    for event in events:
        detail_html = detail_template.render(
            event=event,
            current_year=current_year,
            base_url="../"
        )
        detail_path = os.path.join(EVENTS_OUTPUT_DIR, f"{event['id']}.html")
        with open(detail_path, "w", encoding="utf-8") as f:
            f.write(detail_html)
        print(f"[OK] Generated: {detail_path}")

    print("[SUCCESS] Static site generation completed successfully!")

if __name__ == "__main__":
    generate_site()
