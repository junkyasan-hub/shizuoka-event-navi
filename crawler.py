# -*- coding: utf-8 -*-
"""
浜松市オープンデータ「イベント」を取得し、events.db の item_type='event' の行を
実データで置き換えるクローラー。

データ出典: 静岡県オープンデータカタログ https://opendata.pref.shizuoka.jp/dataset/12874.html
実体: https://static.hamamatsu.odpf.net/opendata/v01/221309_hamamatsu_event/221309_hamamatsu_event.csv
ライセンス: クリエイティブ・コモンズ・ライセンス 表示 4.0 国際 (CC BY 4.0)
  https://opendata.pref.shizuoka.jp/privacy.html の「4．知的財産権の取り扱い」を参照。
  このライセンスに基づき、加工・改変した上で本サイトに掲載している
  （出典表示は templates/app_index.html のフッターに記載）。

くふうロコからの取得と違い、このデータは最初から「自由に二次利用してよい」
公開データなので、利用規約上の問題はない(要出典表示のみ)。

対象は浜松市のみ(現時点でこの形式のオープンデータが確認できたのが浜松市のみのため)。
カテゴリーは「イベント」「おんがく」「スポーツ」に絞り込む
（「そうだん」「けんこう」「職員募集」等の行政サービス系は対象外）。

このスクリプトは手動実行を想定している(スケジューリングは未実装)。
実行方法: python crawler.py
"""
import csv
import datetime
import re
import sqlite3
import urllib.request
import ai_rewriter


DB_PATH = "events.db"
CSV_URL = "https://static.hamamatsu.odpf.net/opendata/v01/221309_hamamatsu_event/221309_hamamatsu_event.csv"
USER_AGENT = "ShizuokaEventNaviBot/1.0 (personal project; manual run; contact: junk.ya.san@gmail.com)"
TARGET_CATEGORIES = {"イベント", "おんがく", "スポーツ"}

CATEGORY_IMAGE = {
    "イベント": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=800&q=80",  # フェス会場
    "おんがく": "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=800&q=80",  # マイク
    "スポーツ": "https://images.unsplash.com/photo-1509941654768-e0a6884be9b2?auto=format&fit=crop&w=800&q=80",  # マラソン
}

WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]


def fetch_csv_rows():
    req = urllib.request.Request(CSV_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    text = raw.decode("cp932")
    reader = csv.DictReader(text.splitlines())
    return list(reader)


def format_date_str(start_date, end_date, start_time, end_time):
    def to_parts(iso_date):
        y, mo, d = (int(x) for x in iso_date.split("-"))
        wd = WEEKDAY_JP[datetime.date(y, mo, d).weekday()]
        return y, mo, d, wd

    sy, sm, sd, swd = to_parts(start_date)
    s = f"{sy}年{sm}月{sd}日({swd})"

    if end_date and end_date != start_date:
        ey, em, ed, ewd = to_parts(end_date)
        if ey == sy:
            s += f" 〜 {em}月{ed}日({ewd})"
        else:
            s += f" 〜 {ey}年{em}月{ed}日({ewd})"

    if start_time:
        s += f" {start_time}"
        if end_time:
            s += f"〜{end_time}"

    return s


def build_fee(basic, detail):
    parts = [p.strip() for p in (basic, detail) if p and p.strip()]
    if not parts:
        return "情報なし（公式サイトをご確認ください）"
    return "・".join(parts)


def build_parking(text):
    text = (text or "").strip()
    if not text:
        return "情報なし（公式サイトをご確認ください）"
    return text


def is_free_parking(parking_text):
    return 1 if "無料" in (parking_text or "") else 0


def transform(row):
    start_date = row["開始日"].strip()
    end_date = row["終了日"].strip()
    date_str = format_date_str(start_date, end_date, row["開始時間"].strip(), row["終了時間"].strip())

    lat_raw, lng_raw = row["緯度"].strip(), row["経度"].strip()
    try:
        lat = float(lat_raw)
    except ValueError:
        lat = 34.7108
    try:
        lng = float(lng_raw)
    except ValueError:
        lng = 137.7261

    address = (row["住所"].strip() + " " + row["方書"].strip()).strip()
    parking = build_parking(row["駐車場情報"])
    category = row["カテゴリー"].strip()

    official_url = row["URL"].strip() or "https://www.hamamatsu-navi.jp/"

    raw_summary = (row["説明"] or "").strip().replace("\r\n", " ").replace("\n", " ")[:120]
    raw_description = (row["説明"] or "").strip()

    # AI リライト処理の呼び出し
    ai_res = ai_rewriter.rewrite_event_info(
        raw_title=row["イベント名"].strip(),
        raw_summary=raw_summary,
        raw_description=raw_description
    )

    organizer = row["主催者"].strip() or row["連絡先名称"].strip()

    return {
        "item_type": "event",
        "title": ai_res["title"],
        "date_str": date_str,
        "location": row["場所名称"].strip(),
        "city": row["市区町村名"].strip() or "浜松市",
        "address": address,
        "lat": lat,
        "lng": lng,
        "google_maps_url": f"https://maps.google.com/?q={lat},{lng}",
        "official_url": official_url,
        "tags": ",".join(ai_res["tags"]) if isinstance(ai_res["tags"], list) else ai_res["tags"],
        "summary": ai_res["summary"],
        "description": ai_res["description"],
        "image_url": CATEGORY_IMAGE.get(category, CATEGORY_IMAGE["イベント"]),
        "fee": build_fee(row["料金(基本)"], row["料金(詳細)"]),
        "organizer": organizer,
        "parking_info": parking,
        "target_age": ai_res["target_age"],
        "is_free_parking": ai_res["is_free_parking"] or is_free_parking(parking),
        "is_stroller_ok": ai_res["is_stroller_ok"],
        "is_rainy_ok": ai_res["is_rainy_ok"],
        "category_scene": ai_res["category_scene"],
    }


def save_to_db(items):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("DELETE FROM events WHERE item_type = 'event'")
    print(f"既存の event 行を {cur.rowcount} 件削除しました。")

    cur.executemany("""
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
    """, items)

    conn.commit()
    conn.close()
    print(f"実イベント {len(items)} 件を登録しました。")


def main():
    print("浜松市オープンデータ「イベント」(CC BY 4.0) を取得します...")
    rows = fetch_csv_rows()
    print(f"CSV全体: {len(rows)} 行")

    today = datetime.date.today().isoformat()
    filtered = [
        r for r in rows
        if r["開始日"].strip() >= today and r["カテゴリー"].strip() in TARGET_CATEGORIES
    ]
    print(f"今日以降 かつ 対象カテゴリー({'/'.join(TARGET_CATEGORIES)}): {len(filtered)} 件")

    items = [transform(r) for r in filtered]
    save_to_db(items)
    print("完了しました。")


if __name__ == "__main__":
    main()
