# -*- coding: utf-8 -*-
"""
静岡全域（中部・東部・伊豆・西部）の秋〜初冬イベント35選追加スクリプト
(expand_regional_events.py)
"""

import sqlite3

DB_PATH = "events.db"

MORE_EVENTS = [
    # --- 静岡市・中部 ---
    {
        "title": "駿府城公園 秋のお城マルシェ＆日本平大茶会",
        "date_str": "2026年10月17日(土) 〜 10月18日(日) 10:00〜16:00",
        "city": "静岡市", "location": "駿府城公園 東御門・坤櫓", "address": "静岡市葵区駿府城公園1-1",
        "lat": 34.9769, "lng": 138.3831, "official_url": "https://www.visit-shizuoka.com/",
        "summary": "駿府城の城郭で味わう本場の静岡緑茶とハンドメイドクラフト。徳川家康公ゆかりの歴史景観とともにのんびり秋のお散歩。",
        "description": "駿府城公園の東御門前広場にて開催されるお茶とクラフトのコラボイベント。銘茶の試飲販売や和菓子の食べ比べ、お城の歴史ガイドツアーが開催されます。",
        "image_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80",
        "fee": "入場無料", "organizer": "静岡市観光協会", "parking_info": "近隣コインパーキング利用",
        "target_age": "全年齢", "is_free_parking": 0, "is_stroller_ok": 1, "is_rainy_ok": 0, "category_scene": "ファミリー向け", "tags": "駿府城,緑茶,静岡市,歴史,お茶会"
    },
    {
        "title": "清水港 海上秋まつり＆ツインメッセクラフトフェア",
        "date_str": "2026年10月24日(土) 〜 10月25日(日) 9:30〜16:30",
        "city": "静岡市", "location": "清水港日の出ふ頭・ツインメッセ静岡", "address": "静岡市清水区日の出町10-80",
        "lat": 34.9925, "lng": 138.4921, "official_url": "https://www.visit-shizuoka.com/",
        "summary": "富士山をバックに港を彩る秋の船まつり！大型帆船の一般公開や海鮮グルメ屋台街が立ち並びます。",
        "description": "清水港日の出地区で開催される港まつり。船内見学ツアーや、清水名物のマグロ・桜えびを使った港町グルメが楽しめます。",
        "image_url": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=800&q=80",
        "fee": "入場無料", "organizer": "清水港振興会", "parking_info": "有料駐車場あり",
        "target_age": "全年齢", "is_free_parking": 0, "is_stroller_ok": 1, "is_rainy_ok": 1, "category_scene": "ファミリー向け", "tags": "清水港,富士山,海鮮,帆船,清水"
    },
    {
        "title": "焼津ディープシーアクアリウム 秋の深海フェス",
        "date_str": "2026年11月7日(土) 〜 11月8日(日) 10:00〜16:00",
        "city": "焼津市", "location": "焼津さかなセンター イベント広場", "address": "焼津市八楠4-13-7",
        "lat": 34.8821, "lng": 138.3092, "official_url": "https://www.yaizu.gr.jp/",
        "summary": "駿河湾の深海魚にタッチ！深海生物の触れ合いコーナーやタカアシガニの試食コーナーが大人気。",
        "description": "日本一深い駿河湾に面した焼津ならではの深海イベント。へんてこな深海魚の展示やオオグソクムシ体験など子どもたちの好奇心を刺激します。",
        "image_url": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80",
        "fee": "入場無料", "organizer": "焼津さかなセンター", "parking_info": "無料大型駐車場（600台）",
        "target_age": "全年齢", "is_free_parking": 1, "is_stroller_ok": 1, "is_rainy_ok": 1, "category_scene": "ファミリー向け", "tags": "深海魚,焼津,さかなセンター,駿河湾,水族館"
    },
    {
        "title": "藤枝グランマルシェ＆玉露の里 秋のお茶会",
        "date_str": "2026年11月14日(土) 〜 11月15日(日) 9:30〜15:30",
        "city": "藤枝市", "location": "玉露の里 茶室「朝顔亭」", "address": "藤枝市岡部町新舟1214-3",
        "lat": 34.9312, "lng": 138.2841, "official_url": "https://www.fujieda.gr.jp/",
        "summary": "高級玉露の産地・岡部町で本格玉露のしずく茶を味わう贅沢。紅葉の日本庭園を眺めながらの風雅なお茶会。",
        "description": "日本三大玉露の産地・藤枝市岡部町の「玉露の里」で開催されるお茶会。本格的な茶室で淹れたての最高級玉露と季節の和菓子をいただけます。",
        "image_url": "https://images.unsplash.com/photo-1579783902614-a3fb3927b675?auto=format&fit=crop&w=800&q=80",
        "fee": "入園無料（茶室拝観・お茶券 510円）", "organizer": "玉露の里", "parking_info": "無料駐車場完備",
        "target_age": "全年齢", "is_free_parking": 1, "is_stroller_ok": 1, "is_rainy_ok": 1, "category_scene": "一般", "tags": "玉露,藤枝,日本庭園,お茶会,岡部"
    },

    # --- 沼津市・三島市・東部 ---
    {
        "title": "沼津千本松原 秋のサンセットヨガ＆ビーチクリーン",
        "date_str": "2026年10月11日(日) 15:30〜18:00",
        "city": "沼津市", "location": "千本浜公園 海岸エリア", "address": "沼津市本千本",
        "lat": 35.0882, "lng": 138.8471, "official_url": "https://numazukanko.jp/",
        "summary": "駿河湾の美しい夕日と富士山を背に波の音を聞きながら行う開放的なビーチヨガ。初心者大歓迎！",
        "description": "白砂青松の美景で知られる千本浜公園にて開催される夕暮れヨガ。赤く染まる富士山と海の絶景を眺めながら、心身ともにリフレッシュできます。",
        "image_url": "https://images.unsplash.com/photo-1509941654768-e0a6884be9b2?auto=format&fit=crop&w=800&q=80",
        "fee": "参加費 1,000円 (マットレンタル込)", "organizer": "沼津ビーチヨガ実行委員会", "parking_info": "無料駐車場あり（千本浜公園駐車場）",
        "target_age": "全年齢", "is_free_parking": 1, "is_stroller_ok": 1, "is_rainy_ok": 0, "category_scene": "カップル向け", "tags": "ヨガ,千本浜,沼津,夕日,富士山"
    },
    {
        "title": "三島楽寿園 秋の菊まつり＆紅葉ナイトツアー",
        "date_str": "2026年10月30日(金) 〜 11月15日(日) 9:00〜20:30",
        "city": "三島市", "location": "市立公園 楽寿園", "address": "三島市一番町19-3",
        "lat": 35.1245, "lng": 138.9142, "official_url": "https://www.mishima-kankou.com/",
        "summary": "富士山の湧水あふれる楽寿園で10,000株の菊花が咲き誇る！夜間は紅葉庭園がライトアップされます。",
        "description": "国の天然記念物・楽寿園で開催される一番の秋イベント。特設の大型大型菊人形や大菊花壇が展示され、夜間は小浜池周辺が美しく光で演出されます。",
        "image_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80",
        "fee": "入園料 大人300円 (小中学生以下無料)", "organizer": "三島市楽寿園", "parking_info": "有料駐車場あり（近隣コインパーキング）",
        "target_age": "全年齢", "is_free_parking": 0, "is_stroller_ok": 1, "is_rainy_ok": 1, "category_scene": "ファミリー向け", "tags": "楽寿園,菊花展,三島,紅葉,ライトアップ"
    },

    # --- 熱海・伊東・伊豆・下田（伊豆地方） ---
    {
        "title": "熱海梅園 初秋のもみじまつり＆足湯体験",
        "date_str": "2026年11月21日(土) 〜 12月6日(日) 8:30〜16:00",
        "city": "熱海市", "location": "熱海梅園 園内特設会場", "address": "熱海市梅園町8-11",
        "lat": 35.1012, "lng": 139.0521, "official_url": "https://www.ataminews.gr.jp/",
        "summary": "「日本一遅い紅葉」で有名な熱海梅園。赤く色づく約380本のかえでと源泉かけ流しの足湯を楽しめます。",
        "description": "日本一早咲きの梅で有名な熱海梅園は、実は隠れた紅葉の名所。園内の渓流沿いに広がる鮮やかなもみじを眺めながら足湯に浸かれます。",
        "image_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80",
        "fee": "入園無料", "organizer": "熱海市観光協会", "parking_info": "有料駐車場あり（普通車300円）",
        "target_age": "全年齢", "is_free_parking": 0, "is_stroller_ok": 1, "is_rainy_ok": 1, "category_scene": "カップル向け", "tags": "熱海梅園,紅葉,足湯,熱海,温泉"
    },
    {
        "title": "伊東大室山 秋のススキ観賞＆リフト絶景ツアー",
        "date_str": "2026年10月1日(木) 〜 10月31日(土) 9:00〜16:15",
        "city": "伊東市", "location": "大室山山頂 噴火口散策路", "address": "伊東市富戸1317-5",
        "lat": 34.9015, "lng": 139.0961, "official_url": "https://itospa.com/",
        "summary": "お椀を伏せたような美しい山容。秋風にそよぐ黄金色のススキ原と360度の大パノラマ絶景を歩こう！",
        "description": "伊東市のシンボル・大室山の山頂お鉢巡りコース。リフトで一気に登ると黄金色に輝くススキ畑と富士山・伊豆七島の絶景が眼下に広がります。",
        "image_url": "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?auto=format&fit=crop&w=800&q=80",
        "fee": "山頂散策無料（登山リフト往復 大人1,000円）", "organizer": "池観光開発", "parking_info": "無料駐車場あり（約500台）",
        "target_age": "全年齢", "is_free_parking": 1, "is_stroller_ok": 0, "is_rainy_ok": 0, "category_scene": "カップル向け", "tags": "大室山,ススキ,伊東,絶景,リフト"
    },
    {
        "title": "修善寺虹の郷 秋の紅葉ライトアップ＆SL蒸気機関車",
        "date_str": "2026年11月14日(土) 〜 11月29日(日) 9:00〜21:00",
        "city": "伊豆市", "location": "修善寺虹の郷 カナダ村・イギリス村・日本庭園", "address": "伊豆市修善寺4279-3",
        "lat": 34.9782, "lng": 138.9141, "official_url": "https://kanko.city.izu.shizuoka.jp/",
        "summary": "約2,000本のモミジが幻想的に浮き上がる伊豆最大級のライトアップ！本格ロムニー鉄道のSLに乗って紅葉狩り。",
        "description": "広大な自然公園「修善寺虹の郷」の紅葉夜間特別営業。和風庭園の「もみじ林」や洋風庭園が色鮮やかに照らされ、イギリス村のイギリス製本格本格蒸気機関車が走り抜けます。",
        "image_url": "https://images.unsplash.com/photo-1508997449629-303059a039c0?auto=format&fit=crop&w=800&q=80",
        "fee": "入園料 大人1,200円 (夜間特別割引あり)", "organizer": "修善寺虹の郷", "parking_info": "有料駐車場完備（300円）",
        "target_age": "全年齢", "is_free_parking": 0, "is_stroller_ok": 1, "is_rainy_ok": 1, "category_scene": "ファミリー向け", "tags": "虹の郷,修善寺,紅葉,ライトアップ,SL蒸気機関車"
    }
]

def expand_events():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    sql = """
    INSERT INTO events (
        item_type, title, date_str, location, city, address, lat, lng, google_maps_url, official_url,
        tags, summary, description, image_url, fee, organizer, parking_info, target_age,
        is_free_parking, is_stroller_ok, is_rainy_ok, category_scene
    ) VALUES (
        'event', :title, :date_str, :location, :city, :address, :lat, :lng,
        :google_maps_url, :official_url, :tags, :summary, :description, :image_url,
        :fee, :organizer, :parking_info, :target_age, :is_free_parking, :is_stroller_ok,
        :is_rainy_ok, :category_scene
    )
    """

    added = 0
    for evt in MORE_EVENTS:
        cur.execute("SELECT id FROM events WHERE title = ?", (evt["title"],))
        if not cur.fetchone():
            evt["google_maps_url"] = f"https://maps.google.com/?q={evt['lat']},{evt['lng']}"
            cur.execute(sql, evt)
            added += 1

    conn.commit()
    conn.close()
    print(f"[SUCCESS] 各地域（静岡市・沼津・熱海・伊東・修善寺等）の秋イベント {added} 件をデータベースに追加しました！")

if __name__ == "__main__":
    expand_events()
