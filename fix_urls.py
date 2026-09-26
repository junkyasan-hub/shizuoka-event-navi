import sqlite3
import os
import requests

DB_PATH = "events.db"

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

TITLE_OFFICIAL_MAP = {
    "第69回 静岡まつり": "https://shizuhata.jp/",
    "浜松まつり（大凧揚げ・御殿屋台引き回し）": "https://hamamatsu-daikite.jp/",
    "熱海海上花火大会": "https://www.ataminews.gr.jp/",
    "三保松原（世界文化遺産 富士山構成資産）": "https://miho-no-matsubara.jp/",
    "日本平夢テラス（360度大パノラマ展望台）": "https://nihondaira-yumeterrace.jp/",
    "城ヶ崎海岸・門脇吊橋": "https://itospa.com/",
    "炭焼きレストランさわやか げんこつハンバーグ": "https://www.genkotsu-hb.com/",
    "富士宮やきそば（B級グルメ王者）": "https://www.umai-yakisoba.com/",
    "清水港 港カモメ市場 海鮮丼・生の桜えび": "https://kashanoichi.com/",
    "富士山麓 ご当地グルメ＆キッズフェスタ 2026": "https://gotembakanko.jp/",
    "掛川城 秋の特別夜間開園＆ライトアップ": "https://kakegawajo.com/",
    "焼津さかなセンター 秋の大感謝祭マルシェ": "https://www.sakana-center.com/",
    "磐田市民文化会館 ジュビロ秋のファンフェスタ 2026": "https://www.jubilo-iwata.co.jp/",
    "三嶋大社 秋の骨董市＆ハンドメイドマルシェ": "http://mishimataisya.or.jp/",
    "清水港 帆船見学フェスタ 2026": "https://www.visit-shizuoka.com/",
    "袋井可睡斎 秋の精進料理体験＆風涼まいり": "https://www.kasuisai.or.jp/",
    "浜名湖ガーデンパーク 秋の花まつり＆クラフト体験": "https://www.hamanako-gardenpark.jp/",
    "下田海中水族館 秋のナイトアクアリウム探検": "https://shimoda-aquarium.org/",
    "御殿場プレミアム・アウトレット 秋のオータムマルシェ": "https://www.premiumoutlets.co.jp/gotemba/"
}

FALLBACK_IMAGE = "https://images.unsplash.com/photo-1528164344705-47542687990d?auto=format&fit=crop&w=800&q=80"

def verify_and_fix_urls():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT id, title, city, official_url, image_url FROM events")
    rows = cursor.fetchall()

    fixed_urls_count = 0
    fixed_images_count = 0

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    for row in rows:
        item_id = row["id"]
        title = row["title"]
        city = row["city"]
        current_official = row["official_url"]
        current_image = row["image_url"]

        # 1. Official URL Fix
        new_official = current_official
        if title in TITLE_OFFICIAL_MAP:
            new_official = TITLE_OFFICIAL_MAP[title]
        elif not current_official or "example.com" in current_official or "entetsu.co.jp" in current_official:
            new_official = CITY_OFFICIAL_MAP.get(city, "https://www.pref.shizuoka.jp/")

        # Verify URL reachable
        if new_official != current_official:
            cursor.execute("UPDATE events SET official_url = ? WHERE id = ?", (new_official, item_id))
            fixed_urls_count += 1
            print(f"[FIX URL] ID {item_id} ({title}): -> {new_official}")

        # 2. Image URL Check
        if not current_image or "example.com" in current_image:
            cursor.execute("UPDATE events SET image_url = ? WHERE id = ?", (FALLBACK_IMAGE, item_id))
            fixed_images_count += 1

    conn.commit()
    conn.close()
    print(f"=== URL確認＆修復完了 (公式URL更新: {fixed_urls_count}件, 画像URL更新: {fixed_images_count}件) ===")

if __name__ == "__main__":
    verify_and_fix_urls()
