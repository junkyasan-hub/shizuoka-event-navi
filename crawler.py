# -*- coding: utf-8 -*-
"""
静岡県お出かけ・イベントナビ 自動収集＆AIリライトクローラー (crawler.py)

【機能概要】
1. 静岡県内の公式オープンデータ・観光情報（浜松市オープンデータ CSV 等）を取得
2. 同一タイトルの既存イベントがあるかをデータベース(events.db)で判定（重複登録の防止）
3. 新規イベントについて、Gemini API (ai_rewriter.py) を呼び出し、著作権に配慮した紹介文にリライト＆属性タグ（駐車場無料、ベビーカー可、雨の日OK等）を自動判定
4. 相手サーバーに負荷をかけないよう time.sleep(2) によるリクエスト制御
5. データベース (events.db) に安全に Upsert（追加・更新）保存
"""

import csv
import datetime
import logging
import os
import re
import sqlite3
import time
import urllib.request
import ai_rewriter

# ログ設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("crawler")

DB_PATH = "events.db"
USER_AGENT = "ShizuokaEventNaviBot/1.0 (+https://github.com/junkyasan-hub/shizuoka-event-navi)"

# 収集対象ソース (浜松市オープンデータ: CC BY 4.0)
HAMAMATSU_CSV_URL = "https://static.hamamatsu.odpf.net/opendata/v01/221309_hamamatsu_event/221309_hamamatsu_event.csv"

# カテゴリ別デフォルト画像（高解像度Unsplash素材）
CATEGORY_IMAGES = {
    "イベント": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=800&q=80",
    "おんがく": "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=800&q=80",
    "スポーツ": "https://images.unsplash.com/photo-1509941654768-e0a6884be9b2?auto=format&fit=crop&w=800&q=80",
    "デフォルト": "https://images.unsplash.com/photo-1528164344705-47542687990d?auto=format&fit=crop&w=800&q=80"
}

WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]

def format_date_str(start_date, end_date, start_time, end_time):
    """日付文字列を「2026年9月12日(土) 〜 9月13日(日) 10:00〜15:00」形式に整形"""
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

def fetch_hamamatsu_opendata():
    """浜松市オープンデータCSVからイベント一覧を取得"""
    logger.info(f"データ取得開始: {HAMAMATSU_CSV_URL}")
    req = urllib.request.Request(HAMAMATSU_CSV_URL, headers={"User-Agent": USER_AGENT})
    
    # サーバー負荷軽減のための間隔保護
    time.sleep(2)

    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    
    text = raw.decode("cp932")
    reader = csv.DictReader(text.splitlines())
    rows = list(reader)
    logger.info(f"取得完了: 全 {len(rows)} 件")
    return rows

def get_existing_event_titles():
    """DB内にすでに登録されているイベントタイトルの集合を取得（重複チェック用）"""
    if not os.path.exists(DB_PATH):
        return set()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT title FROM events WHERE item_type = 'event'")
    titles = {row[0].strip() for row in cur.fetchall() if row[0]}
    conn.close()
    return titles

def save_or_update_events(items):
    """DBへ新しいイベントを保存・更新（スポットやグルメなどの他データは保護）"""
    if not items:
        logger.info("保存対象の新規イベントはありませんでした。")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    upsert_sql = """
    INSERT INTO events (
        item_type, title, date_str, location, city, address, lat, lng, google_maps_url, official_url,
        tags, summary, description, image_url, fee, organizer, parking_info, target_age,
        is_free_parking, is_stroller_ok, is_rainy_ok, category_scene
    )
    VALUES (
        :item_type, :title, :date_str, :location, :city, :address, :lat, :lng, :google_maps_url, :official_url,
        :tags, :summary, :description, :image_url, :fee, :organizer, :parking_info, :target_age,
        :is_free_parking, :is_stroller_ok, :is_rainy_ok, :category_scene
    )
    """

    count_new = 0
    for item in items:
        # 重複チェック（同名イベントがすでにある場合はスキップまたは更新）
        cur.execute("SELECT id FROM events WHERE title = ? AND item_type = 'event'", (item["title"],))
        exists = cur.fetchone()
        
        if not exists:
            cur.execute(upsert_sql, item)
            count_new += 1

    conn.commit()
    conn.close()
    logger.info(f"DB保存完了: 新規 {count_new} 件を追加登録しました。")

def run_crawler():
    """クローラーのメイン実行エントリーポイント"""
    logger.info("=== 静岡県お出かけ・イベントナビ 自動クローラー開始 ===")
    
    # 1. 既存タイトルの取得（AIリライトAPIの無駄消費を防ぐ）
    existing_titles = get_existing_event_titles()
    logger.info(f"DB登録済みイベント数: {len(existing_titles)} 件")

    # 2. オープンデータCSVの取得
    raw_rows = fetch_hamamatsu_opendata()
    
    today_iso = datetime.date.today().isoformat()
    target_categories = {"イベント", "おんがく", "スポーツ"}

    processed_items = []
    
    for row in raw_rows:
        start_date = row.get("開始日", "").strip()
        category = row.get("カテゴリー", "").strip()
        raw_title = row.get("イベント名", "").strip()

        # 今日の日付以降 ＆ 対象カテゴリーのみフィルター
        if not start_date or start_date < today_iso or category not in target_categories:
            continue

        # 3. すでに登録済みの場合はスキップ
        if raw_title in existing_titles:
            continue

        logger.info(f"新規イベント検出: {raw_title} (AIリライト実行中...)")

        raw_summary = (row.get("説明") or "").strip().replace("\r\n", " ").replace("\n", " ")[:120]
        raw_description = (row.get("説明") or "").strip()

        # 4. Gemini API による AI リライト＆タグ分類
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
            "location": row.get("場所名称", "浜松市内").strip(),
            "city": row.get("市区町村名", "浜松市").strip() or "浜松市",
            "address": (row.get("住所", "") + " " + row.get("方書", "")).strip(),
            "lat": lat,
            "lng": lng,
            "google_maps_url": f"https://maps.google.com/?q={lat},{lng}",
            "official_url": row.get("URL", "").strip() or "https://www.hamamatsu-navi.jp/",
            "tags": ",".join(ai_res["tags"]) if isinstance(ai_res["tags"], list) else ai_res["tags"],
            "summary": ai_res["summary"],
            "description": ai_res["description"],
            "image_url": CATEGORY_IMAGES.get(category, CATEGORY_IMAGES["デフォルト"]),
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

    # 5. DBへ一括保存
    save_or_update_events(processed_items)
    logger.info("=== 自動クローラー処理が正常終了しました ===")

if __name__ == "__main__":
    run_crawler()