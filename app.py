import sqlite3
import os
import datetime
import json
import re
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

DB_PATH = "events.db"
TEMPLATES_DIR = "templates"

DATE_RE = re.compile(r'(\d{4})年(\d{1,2})月(\d{1,2})日')
DATE_NO_YEAR_RE = re.compile(r'(\d{1,2})月(\d{1,2})日')

def parse_date_range(date_str):
    """date_str（例:「2026年9月12日(土) 〜 9月13日(日)」）から
    開始日・終了日をISO形式(YYYY-MM-DD)で抽出する。日付が含まれない
    場合（「通年」など）は (None, None) を返す。"""
    m = DATE_RE.search(date_str)
    if not m:
        return None, None
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    start = f"{year:04d}-{month:02d}-{day:02d}"

    rest = date_str[m.end():]
    m_full2 = DATE_RE.search(rest)
    if m_full2:
        # 終了日に年も明記されている場合（年をまたぐ期間など）はそちらを優先
        year2, month2, day2 = int(m_full2.group(1)), int(m_full2.group(2)), int(m_full2.group(3))
        end = f"{year2:04d}-{month2:02d}-{day2:02d}"
    else:
        m2 = DATE_NO_YEAR_RE.search(rest)
        if m2:
            month2, day2 = int(m2.group(1)), int(m2.group(2))
            end = f"{year:04d}-{month2:02d}-{day2:02d}"
        else:
            end = start
    return start, end

app = FastAPI(title="静岡県お出かけ・イベントナビ Webアプリ", version="4.0.0")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

CITY_OFFICIAL_MAP = {
    "静岡市": "https://www.visit-shizuoka.com/",
    "浜松市": "https://www.hamamatsu-navi.jp/",
    "沼津市": "https://numazukanko.jp/",
    "熱海市": "https://www.ataminews.gr.jp/",
    "伊東市": "https://itospa.com/",
    "富士市": "https://www.fujikawarakuza.co.jp/",
    "富士宮市": "https://fujinomiya.gr.jp/",
    "御殿場市": "https://gotemba.jp/",
    "焼津市": "https://www.yaizu.gr.jp/",
    "掛川市": "https://www.kakegawa-kankou.com/",
    "磐田市": "https://kanko-iwata.jp/",
    "三島市": "https://www.mishima-kankou.com/",
    "藤枝市": "https://www.fujieda.gr.jp/",
    "伊豆市": "https://kanko.city.izu.shizuoka.jp/",
    "袋井市": "https://www.fukuroi-kankou.jp/",
    "下田市": "https://www.shimoda-city.info/",
    "島田市": "https://www.shimada-ta.jp/",
    "裾野市": "https://www.city.susono.shizuoka.jp/"
}

def parse_event_status(date_str, start_date, end_date):
    if "通年" in date_str or "常設" in date_str:
        return False, "営業中"

    if not start_date or not end_date:
        return False, "開催予定"

    today = datetime.date.today().isoformat()
    if end_date < today:
        return True, "終了"
    if start_date <= today <= end_date:
        return False, "開催中"
    return False, "開催予定"

def enrich_item(item):
    item = dict(item)

    start_date, end_date = parse_date_range(item["date_str"])
    item["start_date"] = start_date
    item["end_date"] = end_date

    is_ended, status_label = parse_event_status(item["date_str"], start_date, end_date)
    item["is_ended"] = is_ended
    item["status_label"] = status_label

    if not item.get("official_url") or "example.com" in item.get("official_url", ""):
        item["official_url"] = CITY_OFFICIAL_MAP.get(item["city"], "https://www.pref.shizuoka.jp/")

    return item

def extract_calendar_events(items):
    calendar_events = []
    for item in items:
        start_iso = item.get("start_date")
        end_iso = item.get("end_date")

        if start_iso and end_iso and end_iso != start_iso:
            # FullCalendarのendは排他的（実際の終了日の翌日を指定する）
            end_dt = datetime.date.fromisoformat(end_iso) + datetime.timedelta(days=1)
            end_iso = end_dt.isoformat()
        else:
            end_iso = None

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

def fetch_items_from_db(item_type="all", scene=None, free_parking=False, stroller_ok=False, rainy_ok=False, city=None, search=None, date=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM events WHERE 1=1"
    params = []

    if item_type and item_type != "all":
        query += " AND item_type = ?"
        params.append(item_type)

    if scene and scene != "all":
        if scene == "family":
            query += " AND category_scene LIKE '%ファミリー向け%'"
        elif scene == "couple":
            query += " AND category_scene LIKE '%カップル向け%'"
        elif scene == "rainy":
            query += " AND (category_scene LIKE '%雨の日OK%' OR is_rainy_ok = 1)"

    if free_parking:
        query += " AND is_free_parking = 1"

    if stroller_ok:
        query += " AND is_stroller_ok = 1"

    if rainy_ok:
        query += " AND is_rainy_ok = 1"

    if city and city != "all":
        query += " AND city = ?"
        params.append(city)

    if search:
        query += " AND (title LIKE ? OR location LIKE ? OR summary LIKE ? OR tags LIKE ? OR address LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term, term, term])

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    items = [enrich_item(row) for row in rows]

    if date:
        items = [it for it in items if it["start_date"] and it["start_date"] <= date <= it["end_date"]]

    items.sort(key=lambda x: (x["is_ended"], x["id"]))
    return items

def get_all_cities():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT city FROM events ORDER BY city ASC")
    rows = cursor.fetchall()
    conn.close()
    return [row["city"] for row in rows]

@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    item_type: str = Query("all"),
    scene: str = Query("all"),
    free_parking: bool = Query(False),
    stroller_ok: bool = Query(False),
    rainy_ok: bool = Query(False),
    city: str = Query("all"),
    search: str = Query(""),
    date: str = Query("")
):
    items = fetch_items_from_db(
        item_type=item_type,
        scene=scene,
        free_parking=free_parking,
        stroller_ok=stroller_ok,
        rainy_ok=rainy_ok,
        city=city,
        search=search,
        date=date
    )
    cities = get_all_cities()
    calendar_events_json = extract_calendar_events(items)

    return templates.TemplateResponse(
        request=request,
        name="app_index.html",
        context={
            "events": items,
            "calendar_events_json": calendar_events_json,
            "cities": cities,
            "current_item_type": item_type,
            "current_scene": scene,
            "free_parking": free_parking,
            "stroller_ok": stroller_ok,
            "rainy_ok": rainy_ok,
            "current_city": city,
            "search_query": search,
            "current_date": date
        }
    )

@app.get("/api/items")
async def api_items(
    item_type: str = "all",
    scene: str = "all",
    free_parking: bool = False,
    stroller_ok: bool = False,
    rainy_ok: bool = False,
    city: str = "all",
    search: str = "",
    date: str = ""
):
    items = fetch_items_from_db(
        item_type=item_type,
        scene=scene,
        free_parking=free_parking,
        stroller_ok=stroller_ok,
        rainy_ok=rainy_ok,
        city=city,
        search=search,
        date=date
    )
    return JSONResponse(content={"count": len(items), "items": items, "calendar_events": json.loads(extract_calendar_events(items))})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
