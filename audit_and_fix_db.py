# -*- coding: utf-8 -*-
import sqlite3
import requests
import time
from concurrent.futures import ThreadPoolExecutor

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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def is_valid(url):
    if not url or "example.com" in url or not url.startswith("http"):
        return False
    try:
        r = requests.head(url, headers=HEADERS, timeout=1.5, allow_redirects=True)
        return r.status_code < 400
    except Exception:
        return False

def check_record(row):
    r_id, title, city, item_type, official_url, image_url, summary, description = row
    city = city or "静岡市"
    item_type = item_type or "event"

    off_ok = is_valid(official_url)
    img_ok = is_valid(image_url)

    new_off = official_url if off_ok else CITY_OFFICIAL_MAP.get(city, "https://www.pref.shizuoka.jp/")
    new_img = image_url if img_ok else DEFAULT_IMAGES.get(item_type, DEFAULT_IMAGES["event"])

    s = (summary or "").strip()
    d = (description or "").strip()
    if not s and d:
        s = d[:100]
    elif not s and not d:
        s = f"{title}の公式お出かけ情報です。"
        d = s

    return {
        "id": r_id,
        "off_ok": off_ok,
        "new_off": new_off,
        "img_ok": img_ok,
        "new_img": new_img,
        "s": s,
        "d": d,
        "changed": (new_off != official_url) or (new_img != image_url) or (s != summary)
    }

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, title, city, item_type, official_url, image_url, summary, description FROM events")
    rows = cur.fetchall()
    total = len(rows)

    start = time.time()
    with ThreadPoolExecutor(max_workers=30) as ex:
        results = list(ex.map(check_record, rows))

    off_fixes = sum(1 for r in results if not r["off_ok"])
    img_fixes = sum(1 for r in results if not r["img_ok"])
    changed_count = 0

    for r in results:
        if r["changed"]:
            changed_count += 1
            cur.execute("UPDATE events SET official_url = ?, image_url = ?, summary = ?, description = ? WHERE id = ?",
                        (r["new_off"], r["new_img"], r["s"], r["d"], r["id"]))

    conn.commit()
    conn.close()
    elapsed = round(time.time() - start, 2)
    print(f"REPORT: total={total}, off_fixes={off_fixes}, img_fixes={img_fixes}, changed={changed_count}, elapsed={elapsed}s")

if __name__ == "__main__":
    main()
