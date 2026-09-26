# -*- coding: utf-8 -*-
"""既存イベントのリンク切れ official_url を検証済みの正しいURLに修正する。"""
import sqlite3

DB_PATH = "events.db"

FIXES = {
    1: "https://shizuokamatsuri.com/",
    2: "https://hamamatsu-daisuki.net/matsuri/",
    5: "https://nihondaira-yume-terrace.jp/",
    8: "https://umya-yakisoba.com/",
    9: "https://kashinoichi.com/",
    14: "https://itospa.com/",
    15: "https://gotemba.jp/",
    19: "https://www.mishimataisha.or.jp/",
    27: "https://shimoda-aquarium.com/",
}

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for event_id, url in FIXES.items():
        cur.execute("UPDATE events SET official_url = ? WHERE id = ?", (url, event_id))
    conn.commit()
    print(f"Updated {cur.rowcount if cur.rowcount != -1 else len(FIXES)} rows (attempted {len(FIXES)}).")
    conn.close()

if __name__ == "__main__":
    main()
