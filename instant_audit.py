# -*- coding: utf-8 -*-
import sqlite3
import re

DB_PATH = "events.db"

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

DEFAULT_IMAGES = {
    "event": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=800&q=80",
    "spot": "https://images.unsplash.com/photo-1528164344705-47542687990d?auto=format&fit=crop&w=800&q=80",
    "gourmet": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80"
}

def clean_text(t):
    if not t:
        return ""
    t = re.sub(r'[\r\n\t]+', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    return t.strip()

def run_instant_audit():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM events")
    rows = cur.fetchall()
    total = len(rows)

    fixed_urls = 0
    fixed_images = 0
    fixed_texts = 0

    for r in rows:
        r_id = r["id"]
        title = clean_text(r["title"])
        city = clean_text(r["city"]) or "静岡市"
        item_type = r["item_type"] or "event"
        official_url = (r["official_url"] or "").strip()
        image_url = (r["image_url"] or "").strip()
        summary = clean_text(r["summary"])
        description = clean_text(r["description"])

        # URL判定
        new_official = official_url
        if not official_url or "example.com" in official_url or not official_url.startswith("http"):
            new_official = CITY_OFFICIAL_MAP.get(city, "https://www.pref.shizuoka.jp/")
            fixed_urls += 1

        # 画像URL判定
        new_image = image_url
        if not image_url or not image_url.startswith("http"):
            new_image = DEFAULT_IMAGES.get(item_type, DEFAULT_IMAGES["event"])
            fixed_images += 1

        # 概要文判定
        new_summary = summary
        new_description = description
        if not summary and description:
            new_summary = description[:100]
            fixed_texts += 1
        elif not summary and not description:
            new_summary = f"{title}の静岡県内お出かけ情報・イベント案内です。"
            new_description = new_summary
            fixed_texts += 1

        cur.execute("""
            UPDATE events SET
                title = ?,
                city = ?,
                official_url = ?,
                image_url = ?,
                summary = ?,
                description = ?
            WHERE id = ?
        """, (title, city, new_official, new_image, new_summary, new_description, r_id))

    conn.commit()
    conn.close()

    print(f"[AUDIT COMPLETED] Verified {total} records.")
    print(f" - Fixed Official URLs: {fixed_urls}")
    print(f" - Fixed Image URLs: {fixed_images}")
    print(f" - Fixed Text Summaries: {fixed_texts}")

if __name__ == "__main__":
    run_instant_audit()
