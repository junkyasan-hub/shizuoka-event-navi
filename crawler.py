# -*- coding: utf-8 -*-
"""
静岡県全域（中部・東部・伊豆・西部）対応 自動収集＆AIリライトクローラー
(crawler.py)
Uses CSV Open Data and Gemini 3.5 Flash-lite Google Search Grounding to collect
accurate, verified events across Shizuoka prefecture.
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

# 地域別データソース定義 (オープンデータ CSV)
DATA_SOURCES = [
    {
        "region": "西部（浜松）",
        "url": "https://static.hamamatsu.odpf.net/opendata/v01/221309_hamamatsu_event/221309_hamamatsu_event.csv",
        "type": "csv_hamamatsu"
    },
]

# AI自動探索を行う対象地域リスト
AI_DISCOVERY_REGIONS = [
    {
        "region_name": "中部（静岡・志太榛原）",
        "cities": ["静岡市", "焼津市", "藤枝市", "島田市"]
    },
    {
        "region_name": "東部（沼津・三島・富士）",
        "cities": ["沼津市", "三島市", "富士市", "御殿場市"]
    },
    {
        "region_name": "伊豆（熱海・伊東・下田）",
        "cities": ["熱海市", "伊東市", "伊豆市", "下田市", "伊豆の国市"]
    },
    {
        "region_name": "西部（浜松・遠州）",
        "cities": ["浜松市", "磐田市", "袋井市", "掛川市", "湖西市"]
    }
]

# 市区町村ごとの代表緯度経度・画像マッピング
CITY_COORDS = {
    "静岡市": (34.9756, 138.3828),
    "浜松市": (34.7108, 137.7261),
    "沼津市": (35.1003, 138.8596),
    "熱海市": (35.0964, 139.0717),
    "伊東市": (34.9669, 139.0984),
    "富士市": (35.1614, 138.6763),
    "富士宮市": (35.2223, 138.6163),
    "御殿場市": (35.3092, 138.9348),
    "焼津市": (34.8664, 138.3186),
    "藤枝市": (34.8647, 138.2575),
    "三島市": (35.1183, 138.9186),
    "伊豆市": (34.9722, 138.9556),
    "袋井市": (34.7508, 137.9256),
    "掛川市": (34.7708, 137.9956),
    "磐田市": (34.7108, 137.8556),
    "下田市": (34.6781, 138.9453),
    "島田市": (34.8364, 138.1756),
    "伊豆の国市": (35.0381, 138.9453),
}

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
        return 0

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
    return count_new

def run_crawler():
    logger.info("=== 静岡県全域（中部・東部・伊豆・西部）自動クローラー起動 ===")
    existing_titles = get_existing_event_titles()
    logger.info(f"現在DB登録済みイベント数: {len(existing_titles)} 件")

    today_iso = datetime.date.today().isoformat()
    processed_items = []

    # 1. CSV データソースのクローリング
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

                city = row.get("市区町村名", "浜松市").strip() or "浜松市"

                # Gemini 3.5 Flash-lite によるファクトチェック
                ai_res = ai_rewriter.verify_and_rewrite_event(
                    raw_title=raw_title,
                    raw_summary=(row.get("説明") or "")[:120],
                    raw_description=(row.get("説明") or ""),
                    city=city
                )

                if not ai_res.get("is_verified", True):
                    logger.warning(f"実在性が確認できないためスキップ: {raw_title}")
                    continue

                date_str = ai_res.get("date_str") or format_date_str(
                    start_date,
                    row.get("終了日", "").strip(),
                    row.get("開始時間", "").strip(),
                    row.get("終了時間", "").strip()
                )

                coords = CITY_COORDS.get(city, (34.7108, 137.7261))
                try:
                    lat = float(row.get("緯度", coords[0]))
                except ValueError:
                    lat = coords[0]

                try:
                    lng = float(row.get("経度", coords[1]))
                except ValueError:
                    lng = coords[1]

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

    # 2. AI (Gemini 3.5 Flash-lite + Google Search Grounding) による地域別自動探索
    logger.info("AI (Gemini 3.5 Flash-lite) による全域（中部・東部・伊豆・西部）自動イベント探索を開始します...")
    for reg in AI_DISCOVERY_REGIONS:
        r_name = reg["region_name"]
        cities = reg["cities"]
        logger.info(f"地域イベント探索中: [{r_name}] {cities}")
        discovered = ai_rewriter.discover_regional_events(r_name, cities)
        time.sleep(2)  # Rate limiting for Gemini API Free Tier

        for d_item in discovered:
            d_title = d_item.get("title", "").strip()
            if not d_title or d_title in existing_titles:
                continue

            d_city = d_item.get("city", cities[0])
            coords = CITY_COORDS.get(d_city, (34.9756, 138.3828))

            item = {
                "item_type": "event",
                "title": d_title,
                "date_str": d_item.get("date_str", "2026年開催"),
                "location": d_item.get("location", f"{d_city}内"),
                "city": d_city,
                "address": d_item.get("address", d_city),
                "lat": coords[0],
                "lng": coords[1],
                "google_maps_url": f"https://maps.google.com/?q={coords[0]},{coords[1]}",
                "official_url": d_item.get("official_url", "https://www.pref.shizuoka.jp/"),
                "tags": ",".join(d_item["tags"]) if isinstance(d_item.get("tags"), list) else d_item.get("tags", "静岡イベント"),
                "summary": d_item.get("summary", d_title),
                "description": d_item.get("description", d_title),
                "image_url": REGION_IMAGES.get(d_city, REGION_IMAGES["デフォルト"]),
                "fee": d_item.get("fee", "要確認"),
                "organizer": d_item.get("organizer", f"{d_city}観光協会/自治体"),
                "parking_info": d_item.get("parking_info", "情報なし（公式サイトをご確認ください）"),
                "target_age": d_item.get("target_age", "全年齢"),
                "is_free_parking": 1 if d_item.get("is_free_parking") else 0,
                "is_stroller_ok": 1 if d_item.get("is_stroller_ok") else 0,
                "is_rainy_ok": 1 if d_item.get("is_rainy_ok") else 0,
                "category_scene": d_item.get("category_scene", "一般"),
            }
            processed_items.append(item)
            existing_titles.add(d_title)

    save_or_update_events(processed_items)
    logger.info("=== クローラー全行程完了 ===")

if __name__ == "__main__":
    run_crawler()