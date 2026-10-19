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

def parse_event_status(date_str, item_type='event', end_iso='2099-12-31'):
    if item_type in ('spot', 'gourmet') or "通年" in date_str or "常設" in date_str:
        return False, "営業中"
    
    today_iso = datetime.date.today().isoformat()
    if end_iso != '2099-12-31' and end_iso < today_iso:
        return True, "終了"
    
    return False, "開催予定"

SHIZUOKA_SMART_IMAGES = {
    "fuji": "https://images.unsplash.com/photo-1578637387939-43c525550085?auto=format&fit=crop&w=800&q=80",
    "hanabi": "https://images.unsplash.com/photo-1533105079780-92b9be482077?auto=format&fit=crop&w=800&q=80",
    "matsuri": "https://images.unsplash.com/photo-1568832359672-e36cf5d74f54?auto=format&fit=crop&w=800&q=80",
    "tea": "https://images.unsplash.com/photo-1576092768241-dec231879fc3?auto=format&fit=crop&w=800&q=80",
    "gourmet": "https://images.unsplash.com/photo-1579871494447-9811cf80d66c?auto=format&fit=crop&w=800&q=80",
    "unagi": "https://images.unsplash.com/photo-1611143669185-af224c5e3252?auto=format&fit=crop&w=800&q=80",
    "onsen": "https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=800&q=80",
    "ocean": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80",
    "history": "https://images.unsplash.com/photo-1545569341-9eb8b30979d9?auto=format&fit=crop&w=800&q=80",
    "shrine": "https://images.unsplash.com/photo-1607548545892-28df417c0c1b?auto=format&fit=crop&w=800&q=80",
    "music": "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=800&q=80",
    "sports": "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=800&q=80",
    "dance": "https://images.unsplash.com/photo-1508700115892-45ecd05ae2ad?auto=format&fit=crop&w=800&q=80",
    "yoga": "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?auto=format&fit=crop&w=800&q=80",
    "kids": "https://images.unsplash.com/photo-1534567153574-2b12153a87f0?auto=format&fit=crop&w=800&q=80",
    "craft": "https://images.unsplash.com/photo-1513519245088-0e12902e5a38?auto=format&fit=crop&w=800&q=80",
    "autumn": "https://images.unsplash.com/photo-1507781997189-27715f5c35eb?auto=format&fit=crop&w=800&q=80",
    "default": "https://images.unsplash.com/photo-1578637387939-43c525550085?auto=format&fit=crop&w=800&q=80"
}

def get_smart_shizuoka_image(title="", summary="", tags="", city="", item_type=""):
    text = (str(title) + " " + str(summary) + " " + str(tags) + " " + str(city)).lower()
    
    if any(k in text for k in ["富士", "夢テラス", "樹空の森", "朝霧"]):
        return SHIZUOKA_SMART_IMAGES["fuji"]
    if any(k in text for k in ["花火", "キャンドル", "ライトアップ", "イルミネーション", "ナイト"]):
        return SHIZUOKA_SMART_IMAGES["hanabi"]
    if any(k in text for k in ["まつり", "祭", "大たこ", "人形劇", "大道芸", "神楽"]):
        return SHIZUOKA_SMART_IMAGES["matsuri"]
    if any(k in text for k in ["茶", "緑茶", "茶会", "玉露"]):
        return SHIZUOKA_SMART_IMAGES["tea"]
    if any(k in text for k in ["マグロ", "寿司", "海鮮", "サカナ", "キンメダイ", "さわやか", "ハンバーグ", "やきそば", "カキ", "牡蠣", "グルメ", "みかん"]):
        return SHIZUOKA_SMART_IMAGES["gourmet"]
    if any(k in text for k in ["うなぎ", "鰻"]):
        return SHIZUOKA_SMART_IMAGES["unagi"]
    if any(k in text for k in ["温泉", "足湯", "修善寺", "熱海"]):
        return SHIZUOKA_SMART_IMAGES["onsen"]
    if any(k in text for k in ["海", "海岸", "港", "サンセット", "ビーチ", "マリーン", "ボート", "城ヶ崎"]):
        return SHIZUOKA_SMART_IMAGES["ocean"]
    if any(k in text for k in ["城", "万葉", "東照宮", "駿府"]):
        return SHIZUOKA_SMART_IMAGES["history"]
    if any(k in text for k in ["大社", "神社", "寺", "可睡斎"]):
        return SHIZUOKA_SMART_IMAGES["shrine"]
    if any(k in text for k in ["ヨガ", "ピラティス", "ストレッチ"]):
        return SHIZUOKA_SMART_IMAGES["yoga"]
    if any(k in text for k in ["ダンス", "バレエ", "社交ダンス"]):
        return SHIZUOKA_SMART_IMAGES["dance"]
    if any(k in text for k in ["音楽", "ピアノ", "リサイタル", "ジャズ", "吹奏楽", "コンサート", "交響", "ウィーン", "ライアー"]):
        return SHIZUOKA_SMART_IMAGES["music"]
    if any(k in text for k in ["スポーツ", "ボクシング", "相撲", "合気道", "レスリング", "ランニング", "卓球", "アーチェリー", "テニス", "ボートレース", "清走中"]):
        return SHIZUOKA_SMART_IMAGES["sports"]
    if any(k in text for k in ["こども", "ちびっこ", "親子", "わんぱく", "キッズ", "宇宙", "天文台", "星空", "探検"]):
        return SHIZUOKA_SMART_IMAGES["kids"]
    if any(k in text for k in ["クラフト", "マルシェ", "染め", "体験", "工作", "絵手紙", "展示", "写真"]):
        return SHIZUOKA_SMART_IMAGES["craft"]
    if any(k in text for k in ["もみじ", "紅葉", "秋", "菊花", "ススキ"]):
        return SHIZUOKA_SMART_IMAGES["autumn"]
        
    return SHIZUOKA_SMART_IMAGES["default"]

def enrich_item(item):
    item = dict(item)
    start_iso, end_iso = parse_event_dates(item["date_str"], item.get("item_type", "event"))
    item["start_iso"] = start_iso
    item["end_iso"] = end_iso

    is_ended, status_label = parse_event_status(item["date_str"], item.get("item_type", "event"), end_iso)
    item["is_ended"] = is_ended
    item["status_label"] = status_label
    
    # A neutral graphic must not imply that unrelated stock imagery depicts the venue.
    if not item.get("image_url") or "unsplash.com" in item.get("image_url", ""):
        item["image_url"] = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='640' height='360'%3E%3Crect width='640' height='360' fill='%23e9f1e9'/%3E%3Cpath d='M160 270L280 110L400 270Z' fill='%23b6cec0'/%3E%3Ccircle cx='440' cy='110' r='32' fill='%23dbc99c'/%3E%3C/svg%3E"
        item["image_is_placeholder"] = True

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

    if not item.get("lat") or not item.get("lng"):
        json_ld["location"].pop("geo", None)

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
        start_iso = item.get('start_iso')
        end_iso = item.get('end_iso')
        if not start_iso or start_iso == '1970-01-01':
            continue
        # FullCalendar treats end dates as exclusive, including all-day events.
        end_iso = (datetime.date.fromisoformat(end_iso or start_iso)
                   + datetime.timedelta(days=1)).isoformat()

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
                    "officialUrl": item.get("official_url", ""),
                    "date_str": item["date_str"],
                    "city": item["city"]
                }
            }
            if end_iso:
                cal_evt["end"] = end_iso
            calendar_events.append(cal_evt)

    return (json.dumps(calendar_events, ensure_ascii=False)
            .replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026'))

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def fetch_events():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events")
    rows = cursor.fetchall()
    from manual_events import controls
    hidden = controls(conn)
    rows = [r for r in rows if not hidden.get(r["id"], 0)]
    from publication_gate import approved_rows
    rows = approved_rows(conn, rows)
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

    from manual_events import build_editor, controls
    with get_db_connection() as conn:
        # Public output must not contain the full unreviewed database, even in editor JSON.
        with open(os.path.join(OUTPUT_DIR, "manual-editor.html"), "w", encoding="utf-8") as page:
            page.write('<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="robots" content="noindex"><title>管理画面</title><p>編集用データは公開サイトに出力しません。管理環境をご利用ください。</p></html>')
        # ZIP deployment does not delete remote files: replace all unapproved and stale URLs.
        published_ids = {event['id'] for event in events}
        known_ids = {row[0] for row in conn.execute('SELECT id FROM events')}
        known_ids.update(int(path.stem) for path in __import__('pathlib').Path(EVENTS_OUTPUT_DIR).glob('*.html') if path.stem.isdigit())
        for event_id in known_ids - published_ids:
            with open(os.path.join(EVENTS_OUTPUT_DIR, f"{event_id}.html"), "w", encoding="utf-8") as page:
                page.write('<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>掲載情報を確認中</title><main><h1>掲載情報を確認中です</h1><p>公式情報の確認が完了するまで、この情報は掲載を保留しています。イベントの中止を意味するものではありません。</p><a href="../index.html">確認済み情報の一覧へ</a></main></html>')
    print("[SUCCESS] Static site generation completed successfully!")

if __name__ == "__main__":
    generate_site()
