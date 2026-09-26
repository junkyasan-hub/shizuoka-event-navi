# -*- coding: utf-8 -*-
"""
静岡県全域（中部・東部・伊豆・西部）対応 自動収集＆AIリライトクローラー
(crawler.py)
"""

import csv
import datetime
import logging
import os
import sqlite3
import time
import urllib.request
import ai_rewriter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("crawler")

DB_PATH = "events.db"
USER_AGENT = "ShizuokaEventNaviBot/1.0 (+https://github.com/junkyasan-hub/shizuoka-event-navi)"

# 地域別データソース定義
DATA_SOURCES = [
    {
        "region": "西部（浜松）",
        "url": "https://static.hamamatsu.odpf.net/opendata/v01/221309_hamamatsu_event/221309_hamamatsu_event.csv",
        "type": "csv_hamamatsu"
    },
]

# 地域別デフォルト画像
REGION_IMAGES = {
    "静岡市": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80",
    "浜松市": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=800&q=80",
    "沼津市": "https://images.unsplash.com/photo-1534422298391-e4f8c172dddb?auto=format&fit=crop&w=800&q=80",
    "熱海市": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=800&q=80",
    "伊東市": "https://images.unsplash.com/photo-1557800636-894a64c1696f?auto=format&fit=crop&w=800&q=80",
    "デフォルト": "https://images.unsplash.com/photo-1528164344705-47542687990d?auto=format&fit=crop&w=800&q=80"
}

WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]

def format_date_str(start_date, end_date, start_time, end_time):
    def parse_iso(iso_str):
        try:
            parts = [int(x) for x in iso_str.split("-")]
            wd = WEEKDAY_JP[datetime.date(parts[0], parts[1], parts[2]).weekday()]
            return parts[0], parts[1], parts[2], wd
        except Exception:
            return None

    s_parts = parse_iso(start_date)
    if not s_parts:
        return start_date

    sy, sm, sd, swd = s_parts
    res = f"{sy}年{sm}月{sd}日({swd})"

    if end_date and end_date != start_date:
        e_parts = parse_iso(end_date)
        if e_parts:
            ey, em, ed, ewd = e_parts
            if ey == sy:
                res += f" 〜 {em}月{ed}日({ewd})"
            else:
                res += f" 〜 {ey}年{em}月{ed}日({ewd})"

    if start_time:
        res += f" {start_time}"
        if end_time:
            res += f"〜{end_time}"

    return res

def get_existing_event_titles():
    if not os.path.exists(DB_PATH):
        return set()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT title FROM events WHERE item_type = 'event'")
    titles = {row[0].strip() for row in cur.fetchall() if row[0]}
    conn.close()
    return titles

def save_or_update_events(items):
    if not items:
        logger.info("新規登録対象のイベントはありませんでした。")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    upsert_sql = """
    INSERT INTO events (
        item_type, title, date_str, location, city, address, lat, lng, google_maps_url, official_url,
        tags, summary, description, image_url, fee, organizer, parking_info, target_age,
        is_free_parking, is_stroller_ok, is_rainy_ok, category_scene
    ) VALUES (
        :item_type, :title, :date_str, :location, :city, :address, :lat, :lng, :google_maps_url, :official_url,
        :tags, :summary, :description, :image_url, :fee, :organizer, :parking_info, :target_age,
        :is_free_parking, :is_stroller_ok, :is_rainy_ok, :category_scene
    )
    """

    count_new = 0
    for item in items:
        cur.execute("SELECT id FROM events WHERE title = ? AND item_type = 'event'", (item["title"],))
        if not cur.fetchone():
            cur.execute(upsert_sql, item)
            count_new += 1

    conn.commit()
    conn.close()
    logger.info(f"全域データ保存完了: 新規 {count_new} 件を追加登録しました。")

def run_crawler():
    logger.info("=== 静岡県全域（中部・東部・伊豆・西部）自動クローラー起動 ===")
    existing_titles = get_existing_event_titles()
    logger.info(f"現在DB登録済みイベント数: {len(existing_titles)} 件")

    today_iso = datetime.date.today().isoformat()
    processed_items = []

    for source in DATA_SOURCES:
        logger.info(f"データソース取得中: [{source['region']}] {source['url']}")
        time.sleep(2)  # 相手サーバー負荷軽減

        try:
            req = urllib.request.Request(source["url"], headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw_text = resp.read().decode("cp932")

            reader = csv.DictReader(raw_text.splitlines())
            target_categories = {"イベント", "おんがく", "スポーツ"}

            for row in reader:
                start_date = row.get("開始日", "").strip()
                category = row.get("カテゴリー", "").strip()
                raw_title = row.get("イベント名", "").strip()

                if not start_date or start_date < today_iso or category not in target_categories:
                    continue

                if raw_title in existing_titles:
                    continue

                logger.info(f"新規イベント検出: {raw_title} (AIリライト実行)")

                raw_summary = (row.get("説明") or "").strip().replace("\r\n", " ").replace("\n", " ")[:120]
                raw_description = (row.get("説明") or "").strip()

                # Gemini API リライト
                ai_res = ai_rewriter.rewrite_event_info(
                    raw_title=raw_title,
                    raw_summary=raw_summary,
                    raw_description=raw_description
                )

                date_str = format_date_str(
                    start_date,
                    row.get("終了日", "").strip(),
                    row.get("開始時間", "").strip(),
                    row.get("終了時間", "").strip()
                )

                city = row.get("市区町村名", "浜松市").strip() or "浜松市"

                try:
                    lat = float(row.get("緯度", 34.7108))
                except ValueError:
                    lat = 34.7108

                try:
                    lng = float(row.get("経度", 137.7261))
                except ValueError:
                    lng = 137.7261

                parking_info = (row.get("駐車場情報") or "情報なし（公式サイトをご確認ください）").strip()
                fee_basic = (row.get("料金(基本)") or "").strip()
                fee_detail = (row.get("料金(詳細)") or "").strip()
                fee = "・".join([f for f in [fee_basic, fee_detail] if f]) or "情報なし"

                item = {
                    "item_type": "event",
                    "title": ai_res["title"],
                    "date_str": date_str,
                    "location": row.get("場所名称", f"{city}内").strip(),
                    "city": city,
                    "address": (row.get("住所", "") + " " + row.get("方書", "")).strip(),
                    "lat": lat,
                    "lng": lng,
                    "google_maps_url": f"https://maps.google.com/?q={lat},{lng}",
                    "official_url": row.get("URL", "").strip() or "https://www.pref.shizuoka.jp/",
                    "tags": ",".join(ai_res["tags"]) if isinstance(ai_res["tags"], list) else ai_res["tags"],
                    "summary": ai_res["summary"],
                    "description": ai_res["description"],
                    "image_url": REGION_IMAGES.get(city, REGION_IMAGES["デフォルト"]),
                    "fee": fee,
                    "organizer": row.get("主催者", "").strip() or row.get("連絡先名称", "").strip() or "主催者情報なし",
                    "parking_info": parking_info,
                    "target_age": ai_res["target_age"],
                    "is_free_parking": ai_res["is_free_parking"],
                    "is_stroller_ok": ai_res["is_stroller_ok"],
                    "is_rainy_ok": ai_res["is_rainy_ok"],
                    "category_scene": ai_res["category_scene"],
                }

                processed_items.append(item)

        except Exception as e:
            logger.error(f"データソース取得エラー [{source['region']}]: {e}")

    save_or_update_events(processed_items)
    logger.info("=== クローラー全行程完了 ===")

if __name__ == "__main__":
    run_crawler()