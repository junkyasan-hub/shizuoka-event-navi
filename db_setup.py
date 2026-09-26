import sqlite3
import os

DB_PATH = "events.db"

def init_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_type TEXT DEFAULT 'event', -- 'event', 'spot', 'gourmet'
        title TEXT NOT NULL,
        date_str TEXT NOT NULL,
        location TEXT NOT NULL,
        city TEXT NOT NULL,
        address TEXT DEFAULT '',
        lat REAL DEFAULT 0.0,
        lng REAL DEFAULT 0.0,
        google_maps_url TEXT DEFAULT '',
        official_url TEXT DEFAULT '',
        tags TEXT NOT NULL,
        summary TEXT NOT NULL,
        description TEXT NOT NULL,
        image_url TEXT NOT NULL,
        fee TEXT NOT NULL,
        organizer TEXT NOT NULL,
        parking_info TEXT DEFAULT '近隣駐車場あり',
        target_age TEXT DEFAULT '全年齢',
        is_free_parking INTEGER DEFAULT 0,
        is_stroller_ok INTEGER DEFAULT 0,
        is_rainy_ok INTEGER DEFAULT 0,
        category_scene TEXT DEFAULT 'ファミリー向け',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    sample_items = [
        # --- イベント (Events) ---
        (
            "event",
            "第69回 静岡まつり",
            "2026年4月3日(金) 〜 4月5日(日)",
            "駿府城公園、静岡市市街地",
            "静岡市",
            "静岡県静岡市葵区駿府城公園1-1",
            34.9792, 138.3833,
            "https://maps.google.com/?q=34.9792,138.3833",
            "https://shizuhata.jp/",
            "お祭り, 歴史, 桜, 春イベント",
            "徳川家康公が家臣を連れて花見をしたという故事にちなんだ、静岡市を代表する春の風物詩です。",
            "「ここが駿府城、ここが家康公の城下町」をテーマに、豪華絢爛な「大御所花見行列」や「大御所夜桜乱舞」など見どころが満載です。",
            "https://images.unsplash.com/photo-1528164344705-47542687990d?auto=format&fit=crop&w=800&q=80",
            "観覧無料",
            "静岡まつり実行委員会",
            "周辺の有料駐車場をご利用ください",
            "全年齢（ファミリー・シニア）",
            0, 1, 0,
            "ファミリー向け,カップル向け"
        ),
        (
            "event",
            "浜松まつり（大凧揚げ・御殿屋台引き回し）",
            "2026年5月3日(日) 〜 5月5日(火)",
            "中田島砂丘、浜松市中心部",
            "浜松市",
            "静岡県浜松市中央区中田島町",
            34.6653, 137.7508,
            "https://maps.google.com/?q=34.6653,137.7508",
            "https://hamamatsu-daikite.jp/",
            "お祭り, 伝統, 熱気, GW",
            "端午の節句にちなみ、子供の誕生を祝って大凧を揚げる熱気あふれる初子祝いの伝統行事です。",
            "昼間は中田島砂丘の広大な大空に巨大な凧が舞い上がり、夜は絢爛豪華な「御殿屋台」が街を彩ります。",
            "https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&w=800&q=80",
            "入場無料",
            "浜松まつり組織委員会",
            "臨時無料駐車場あり（シャトルバス運行）",
            "全年齢（子育てファミリー推奨）",
            1, 1, 0,
            "ファミリー向け"
        ),
        (
            "event",
            "熱海海上花火大会",
            "2026年4月19日(日) 20:20〜20:40",
            "熱海サンビーチ沿岸",
            "熱海市",
            "静岡県熱海市東海岸町",
            35.0964, 139.0768,
            "https://maps.google.com/?q=35.0964,139.0768",
            "https://www.ataminews.gr.jp/event/208/",
            "花火, 絶景, 温泉, ナイトイベント",
            "年間を通して開催される熱海名物の海上花火大会。フィナーレの「大空中ナイアガラ」は圧巻です。",
            "山に囲まれたすり鉢状の熱海湾の地形が生み出す音響効果は、大迫力の音響とド迫力の花火を体験できます。",
            "https://images.unsplash.com/photo-1498931299472-f7a63a5a1cfa?auto=format&fit=crop&w=800&q=80",
            "観覧無料",
            "熱海温泉ホテル旅館協同組合",
            "市営有料駐車場あり（サンビーチ前）",
            "大人・カップル・小学生以上",
            0, 1, 0,
            "カップル向け,ファミリー向け"
        ),

        # --- 定番スポット (Classic Spots) ---
        (
            "spot",
            "三保松原（世界文化遺産 富士山構成資産）",
            "通年（24時間散策可能）",
            "三保松原海岸",
            "静岡市",
            "静岡県静岡市清水区三保1338-45",
            34.9972, 138.5239,
            "https://maps.google.com/?q=34.9972,138.5239",
            "https://miho-no-matsubara.jp/",
            "絶景, 富士山, 世界遺産, 散策, 自然",
            "約7kmの海岸に約3万本の松が生い茂り、松林の向こうに富士山を望む日本屈指の景勝地です。",
            "天女の羽衣伝説で知られる「羽衣の松」や、みほしるべ（文化鑑賞施設）があり、絵画のような風景を楽しめます。",
            "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?auto=format&fit=crop&w=800&q=80",
            "見学無料",
            "静岡市文化財課 / 三保松原みほしるべ",
            "無料駐車場あり（約200台）",
            "全年齢（ファミリー・カップル・シニア）",
            1, 1, 0,
            "ファミリー向け,カップル向け"
        ),
        (
            "spot",
            "日本平夢テラス（360度大パノラマ展望台）",
            "9:00〜17:00（土曜日は21:00まで）",
            "日本平山頂",
            "静岡市",
            "静岡県静岡市清水区草薙600-1",
            34.9725, 138.4678,
            "https://maps.google.com/?q=34.9725,138.4678",
            "https://nihondaira-yumeterrace.jp/",
            "絶景, 富士山, 建築デザイン, 展望台, 建築",
            "隈研吾建築都市設計事務所による美しい木造建築と、富士山・駿河湾・伊豆半島を見渡す360度の大パノラマ。",
            "1階は歴史展示コーナー、2階はラウンジ、3階は展望フロア。約200mの展望回廊からは四季折々の景色や夜景を堪能できます。",
            "https://images.unsplash.com/photo-1503899036084-c55cdd92da26?auto=format&fit=crop&w=800&q=80",
            "入場無料",
            "日本平夢テラス管理事務所",
            "無料駐車場あり（約140台完備）",
            "全年齢（バリアフリー完備）",
            1, 1, 1,
            "カップル向け,雨の日OK,ファミリー向け"
        ),
        (
            "spot",
            "城ヶ崎海岸・門脇吊橋",
            "通年散策可能",
            "城ヶ崎海岸",
            "伊東市",
            "静岡県伊東市富戸",
            34.8986, 139.1333,
            "https://maps.google.com/?q=34.8986,139.1333",
            "https://itospa.com/",
            "絶景, 吊橋, スリル, 海, 海岸散策",
            "約4000年前に大室山が噴火した際の溶岩が作られた断崖絶壁と、スリル満点の門脇吊橋。",
            "高さ23m、長さ48mの門脇吊橋からは足元に打ち寄せる荒波が見え、スリル満点！門脇埼灯台からは伊豆諸島や天城連山が一望できます。",
            "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80",
            "散策自由・無料",
            "伊東市観光案内所",
            "門脇駐車場あり（有料・乗用車500円）",
            "小学生以上〜大人・カップル",
            0, 0, 0,
            "カップル向け,ファミリー向け"
        ),

        # --- 定番グルメ (Gourmet) ---
        (
            "gourmet",
            "炭焼きレストランさわやか げんこつハンバーグ",
            "11:00〜22:00",
            "静岡県内全34店舗",
            "静岡市",
            "静岡県静岡市葵区盛一町10-25（新静岡セノバ店・葵店他）",
            34.9744, 138.3867,
            "https://maps.google.com/?q=34.9744,138.3867",
            "https://www.genkotsu-hb.com/",
            "グルメ, ハンバーグ, 静岡名物, 行列店, ソウルフード",
            "静岡県民のソウルフード！備長炭で焼き上げる牛肉100%の極上「げんこつハンバーグ」。",
            "目の前で半分にカットし、熱々の鉄板でジューと焼き上げるパフォーマンスは圧巻。オニオンソースとの組み合わせは病みつきになります。",
            "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80",
            "げんこつハンバーグ 1,265円〜",
            "さわやか株式会社",
            "各店舗無料駐車場あり（セノバ店除く）",
            "全年齢（ファミリー大人気）",
            1, 1, 1,
            "ファミリー向け,雨の日OK,カップル向け"
        ),
        (
            "gourmet",
            "富士宮やきそば（B級グルメ王者）",
            "10:00〜18:00",
            "富士宮市内・お宮横丁",
            "富士宮市",
            "静岡県富士宮市宮町4-23（お宮横丁）",
            35.2269, 138.6111,
            "https://maps.google.com/?q=35.2269,138.6111",
            "https://www.umai-yakisoba.com/",
            "グルメ, B級グルメ, ご当地ソウルフード, 富士宮",
            "コシの強い角麺、蒸し麺、肉かす、削り粉が織りなすB級グルメグランプリ初代王者！",
            "富士山の湧水で仕込まれたもちもちの麺に、香ばしい削り粉をたっぷりかけて味わう至高の焼きそば。",
            "https://images.unsplash.com/photo-1612929633738-8fe44f7ec841?auto=format&fit=crop&w=800&q=80",
            "1人前 500円〜700円前後",
            "富士宮やきそば学会",
            "浅間大社駐車場（有料）利用",
            "全年齢",
            0, 1, 1,
            "ファミリー向け,雨の日OK"
        ),
        (
            "gourmet",
            "清水港 港カモメ市場 海鮮丼・生の桜えび",
            "10:00〜20:00",
            "清水港 河岸の市",
            "静岡市",
            "静岡県静岡市清水区島崎町149",
            35.0167, 138.4894,
            "https://maps.google.com/?q=35.0167,138.4894",
            "https://kashanoichi.com/",
            "グルメ, 海鮮丼, マグロ, 桜えび, 港町",
            "日本一の水揚げ量を誇る清水港の新鮮なまぐろと、駿河湾特産の生桜えび・生しらすを堪能！",
            "「魚市場食堂」や「まぐろ館」など鮮魚店直営の食事処がずらり。溢れんばかりのマグロ丼や桜えびかき揚げ丼は絶品です。",
            "https://images.unsplash.com/photo-1534422298391-e4f8c172dddb?auto=format&fit=crop&w=800&q=80",
            "海鮮丼 1,200円〜2,500円",
            "清水港 河岸の市",
            "有料駐車場あり（館内利用割引あり）",
            "全年齢（全天候型市場）",
            0, 1, 1,
            "カップル向け,雨の日OK,ファミリー向け"
        )
    ]

    cursor.executemany("""
    INSERT INTO events (
        item_type, title, date_str, location, city, address, lat, lng, google_maps_url, official_url,
        tags, summary, description, image_url, fee, organizer, parking_info, target_age,
        is_free_parking, is_stroller_ok, is_rainy_ok, category_scene
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, sample_items)

    conn.commit()
    conn.close()
    print(f"Database reset with official_url support across {len(sample_items)} items!")

if __name__ == "__main__":
    init_db()
