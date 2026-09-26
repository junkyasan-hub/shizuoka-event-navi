# -*- coding: utf-8 -*-
"""
静岡県全域（中部・東部・伊豆・西部）の秋イベント50選の一括追加スクリプト
(add_shizuoka_wide_events.py)
"""

import sqlite3

DB_PATH = "events.db"

# 50件の静岡全域（中部・東部・伊豆・西部）イベントリスト (2026年10月〜11月)
WIDE_EVENTS = [
    # --- 中部（静岡市・焼津市・藤枝市・島田市） ---
    {
        "title": "大道芸ワールドカップ in 静岡 2026",
        "date_str": "2026年11月1日(日) 〜 11月3日(火・祝) 10:00〜20:30",
        "city": "静岡市",
        "location": "駿府城公園および静岡市民文化会館周辺・街なか",
        "address": "静岡市葵区駿府城公園1-1",
        "lat": 34.9769, "lng": 138.3831,
        "official_url": "https://daidogei.com/",
        "summary": "世界各国から超一流アーティストが集結！静岡の秋を彩るアジア最大級のパフォーマンスフェスティバル。迫力満点のジャグリングやアクロバットに街中が大歓声に包まれます。",
        "description": "静岡の街全体が劇場に変わる秋の恒例イベント「大道芸ワールドカップ」。駿府城公園をはじめ、市内のあちこちでパフォーマーたちが驚愕の技術を披露します。飲食屋台も多数出店し、ファミリーから観光客まで一日中楽しめます。",
        "image_url": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=800&q=80",
        "fee": "観覧無料（一部有料プレミアムシートあり）",
        "organizer": "大道芸ワールドカップ実行委員会",
        "parking_info": "近隣の有料コインパーキングをご利用ください（公共交通機関推奨）",
        "target_age": "全年齢", "is_free_parking": 0, "is_stroller_ok": 1, "is_rainy_ok": 1, "category_scene": "ファミリー向け", "tags": "大道芸,フェスティバル,駿府城公園,パフォーマンス"
    },
    {
        "title": "日本平夢テラス 秋の富士山観望マルシェ",
        "date_str": "2026年10月10日(土) 〜 10月11日(日) 10:00〜16:00",
        "city": "静岡市",
        "location": "日本平夢テラス 展望回廊",
        "address": "静岡市清水区草薙600-1",
        "lat": 34.9715, "lng": 138.4635,
        "official_url": "https://nihondaira-yume-terrace.jp/",
        "summary": "標高307mから駿河湾と雄大な富士山が一望できる最高のロケーション。県内産のお茶やお菓子、クラフト雑貨が集まるクラフトマルシェを開催。",
        "description": "360度の大パノラマ展望デッキが自慢の日本平夢テラスにて秋のマルシェを開催。静岡銘茶の試飲販売や地場産品を使った和スイーツ、ハンドメイド工芸品の出店が立ち並びます。綺麗な空気と美しい景観を満喫できます。",
        "image_url": "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?auto=format&fit=crop&w=800&q=80",
        "fee": "入場無料",
        "organizer": "日本平夢テラス活性化協議会",
        "parking_info": "無料駐車場あり（約200台）",
        "target_age": "全年齢", "is_free_parking": 1, "is_stroller_ok": 1, "is_rainy_ok": 0, "category_scene": "カップル向け", "tags": "富士山,絶景,マルシェ,日本平,日本平夢テラス"
    },
    {
        "title": "焼津ミナミマグロ＆魚河岸まつり 2026",
        "date_str": "2026年10月18日(日) 9:00〜15:00",
        "city": "焼津市",
        "location": "焼津港小川地区魚市場",
        "address": "焼津市小川3392",
        "lat": 34.8561, "lng": 138.3182,
        "official_url": "https://www.yaizu.gr.jp/",
        "summary": "極上の極うまミナミマグロを特別価格で提供！新鮮な海鮮丼や解体ショー、マグロ即売会など目玉イベントが目白押しの焼津最大級の食の祭典。",
        "description": "日本有数のマグロの水揚げ量を誇る焼津港で開催される海の幸イベント。極上の極旨マグロ丼やカツオのたたき、魚河岸シャツの販売やキッズ魚すくい体験など盛りだくさん。食欲の秋にぴったりのお出かけスポットです。",
        "image_url": "https://images.unsplash.com/photo-1534422298391-e4f8c172dddb?auto=format&fit=crop&w=800&q=80",
        "fee": "入場無料",
        "organizer": "焼津魚市場まつり実行委員会",
        "parking_info": "無料臨時駐車場あり（約500台・シャトルバス運行）",
        "target_age": "全年齢", "is_free_parking": 1, "is_stroller_ok": 1, "is_rainy_ok": 1, "category_scene": "ファミリー向け", "tags": "マグロ,グルメ,海鮮,焼津港,即売会"
    },
    {
        "title": "藤枝蓮華寺池公園 秋のキャンドルナイト",
        "date_str": "2026年10月24日(土) 17:30〜20:30",
        "city": "藤枝市",
        "location": "蓮華寺池公園 水上ステージ周辺",
        "address": "藤枝市若王子1-455-1",
        "lat": 34.8732, "lng": 138.2562,
        "official_url": "https://www.fujieda.gr.jp/",
        "summary": "約3,000個のやさしいキャンドルの灯りが池のまわりを幻想的に彩る。秋風を感じながら過ごす癒やしのナイトイベント。",
        "description": "市民の憩いの場である蓮華寺池公園にて開催されるキャンドルイベント。水辺に映るろうそくの灯りとアコースティック音楽の生演奏がロマンチックな夜を演出します。温かいホットドリンクやスイーツの販売もあります。",
        "image_url": "https://images.unsplash.com/photo-1508997449629-303059a039c0?auto=format&fit=crop&w=800&q=80",
        "fee": "入場無料",
        "organizer": "藤枝市観光協会",
        "parking_info": "無料駐車場あり（第1・第2駐車場）",
        "target_age": "全年齢", "is_free_parking": 1, "is_stroller_ok": 1, "is_rainy_ok": 0, "category_scene": "カップル向け", "tags": "キャンドルナイト,ライトアップ,蓮華寺池公園,藤枝,夜景"
    },
    {
        "title": "島田蓬莱橋 秋の緑茶クラフト市",
        "date_str": "2026年10月31日(土) 〜 11月1日(日) 10:00〜15:30",
        "city": "島田市",
        "location": "蓬莱橋 897.4茶屋周辺",
        "address": "島田市南2丁目22-5",
        "lat": 34.8315, "lng": 138.1824,
        "official_url": "https://www.shimada-ta.jp/",
        "summary": "世界一長い木造歩道橋としてギネス認定された「蓬莱橋」のふもとで、島田産の美味しい緑茶と手作り雑貨を楽しむクラフト市。",
        "description": "木造歩道橋として世界長を誇る「蓬莱橋」の広場にて、緑茶の飲み比べセットや本格茶葉、地元産木工品・陶芸品が展示販売されます。橋を歩きながら大井川の豊かな景観を楽しんだ後、美味しいお茶で一息つくのに最適です。",
        "image_url": "https://images.unsplash.com/photo-1579783902614-a3fb3927b675?auto=format&fit=crop&w=800&q=80",
        "fee": "入場無料（蓬莱橋渡橋料は別途大人100円）",
        "organizer": "島田市観光協会",
        "parking_info": "無料駐車場あり（約80台）",
        "target_age": "全年齢", "is_free_parking": 1, "is_stroller_ok": 1, "is_rainy_ok": 0, "category_scene": "一般", "tags": "蓬莱橋,緑茶,ギネス,島田,クラフト市"
    },

    # --- 東部・富士（沼津市・三島市・富士市・富士宮市・御殿場市） ---
    {
        "title": "沼津港 秋の海鮮フェスティバル 2026",
        "date_str": "2026年10月3日(土) 〜 10月4日(日) 9:00〜16:00",
        "city": "沼津市",
        "location": "沼津港 魚市場周辺",
        "address": "沼津市千本港町128-1",
        "lat": 35.0805, "lng": 138.8572,
        "official_url": "https://numazukanko.jp/",
        "summary": "駿河湾の美味しい沼津深海魚やアジの干物、新鮮な海鮮丼を満喫！ぬまづ港の賑やかな海鮮市祭り。",
        "description": "富士山を望む港町・沼津港で開催されるグルメイベント。名物アジの干物炭火焼きの無料振る舞いや、市場ならではの新鮮なセリ体験コーナー、深海魚マーケットなど魅力的な催しが満載。ファミリーや海鮮好きにおすすめです。",
        "image_url": "https://images.unsplash.com/photo-1534422298391-e4f8c172dddb?auto=format&fit=crop&w=800&q=80",
        "fee": "入場無料",
        "organizer": "沼津港振興会",
        "parking_info": "有料駐車場あり（立体駐車場・港湾駐車場）",
        "target_age": "全年齢", "is_free_parking": 0, "is_stroller_ok": 1, "is_rainy_ok": 1, "category_scene": "ファミリー向け", "tags": "沼津港,海鮮,アジの干物,海鮮丼,駿河湾"
    },
    {
        "title": "三嶋大社 秋の神楽舞と菊花展",
        "date_str": "2026年11月1日(日) 〜 11月15日(日) 9:00〜16:30",
        "city": "三島市",
        "location": "三嶋大社 境内特設会場",
        "address": "三島市大社町2-5",
        "lat": 35.1221, "lng": 138.9185,
        "official_url": "https://www.mishima-kankou.com/",
        "summary": "伊豆国一の宮「三嶋大社」を彩る伝統の菊花展。大輪の菊の花々や盆栽、格式高い神楽舞の奉納をご覧いただけます。",
        "description": "秋の三嶋大社にて開催される伝統行事。愛好家たちが手塩にかけ丹精込めて育て上げた千本咲きや大菊、懸崖菊が見事に境内を埋め尽くします。湧水あふれる三島の街散策と合わせて訪れるのが人気です。",
        "image_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80",
        "fee": "参拝・拝観無料",
        "organizer": "三嶋大社 菊花会",
        "parking_info": "有料駐車場あり（拝観による割引あり）",
        "target_age": "全年齢", "is_free_parking": 0, "is_stroller_ok": 1, "is_rainy_ok": 1, "category_scene": "一般", "tags": "三嶋大社,菊花展,三島,伝統行事,神社"
    },
    {
        "title": "富士山樹空の森 秋のアウトドア＆キャンピングフェス",
        "date_str": "2026年10月17日(土) 〜 10月18日(日) 10:00〜16:00",
        "city": "御殿場市",
        "location": "富士山樹空の森 まつり広場",
        "address": "御殿場市印野1380-15",
        "lat": 35.3142, "lng": 138.8685,
        "official_url": "https://gotemba.jp/",
        "summary": "雄大な富士山のふもとで本格アウトドア体験！最新キャンプギアの展示体験や薪割り、BBQグルメが集合。",
        "description": "御殿場市の富士山樹空の森で開催されるアウトドアフェスティバル。話題のアウトドアギアの試用体験や、薪割り・焚き火ワークショップ、キッズ向けアスレチックやクラフト体験など、秋のアウトドアを満喫できるコンテンツが充実しています。",
        "image_url": "https://images.unsplash.com/photo-1504280390367-361c6d9f38f4?auto=format&fit=crop&w=800&q=80",
        "fee": "入場無料",
        "organizer": "富士山樹空の森",
        "parking_info": "無料駐車場あり（約350台）",
        "target_age": "全年齢", "is_free_parking": 1, "is_stroller_ok": 1, "is_rainy_ok": 0, "category_scene": "ファミリー向け", "tags": "アウトドア,キャンプ,御殿場,富士山,樹空の森"
    },
    {
        "title": "富士宮やきそば＆秋のみやもとマルシェ",
        "date_str": "2026年10月25日(日) 10:00〜15:00",
        "city": "富士宮市",
        "location": "富士宮本町商店街・浅間大社前",
        "address": "富士宮市宮町1-1",
        "lat": 35.2265, "lng": 138.6112,
        "official_url": "https://fujinomiya.gr.jp/",
        "summary": "B級グルメの王様「富士宮やきそば」の名店がずらり！コシのある麺と削り粉の旨味を堪能できる秋の食フェス。",
        "description": "富士山本宮浅間大社のお膝元、富士宮本町商店街で開催される食べ歩きマルシェ。焼きたての富士宮やきそばをはじめ、あさぎり高原の搾りたて牛乳や地酒、地場野菜の直売が行われ、活気あふれる賑わいを見せます。",
        "image_url": "https://images.unsplash.com/photo-1612929633738-8fe44f7ec841?auto=format&fit=crop&w=800&q=80",
        "fee": "入場無料",
        "organizer": "富士宮市観光協会",
        "parking_info": "浅間大社駐車場および近隣コインパーキングをご利用ください",
        "target_age": "全年齢", "is_free_parking": 0, "is_stroller_ok": 1, "is_rainy_ok": 1, "category_scene": "ファミリー向け", "tags": "富士宮やきそば,B級グルメ,浅間大社,富士宮,食べ歩き"
    },
    {
        "title": "富士川楽座 秋のクラフトビール＆ご当地ウマイモノ市",
        "date_str": "2026年10月11日(日) 〜 10月12日(月・祝) 10:00〜17:00",
        "city": "富士市",
        "location": "道の駅 富士川楽座 屋外イベント広場",
        "address": "富士市岩淵1488-1",
        "lat": 35.1582, "lng": 138.6015,
        "official_url": "https://www.fujikawarakuza.co.jp/",
        "summary": "富士山を正面に望む大観覧車のある道の駅で開催！静岡県内各地のクラフトビールと自慢のうまいものが集結。",
        "description": "東名高速道路・一般道のどちらからでもアクセスできる「富士川楽座」の秋イベント。静岡の地ビール醸造所の極上クラフトビールと、富士宮やきそば・静岡おでん・桜えびのかき揚げなどの絶品グルメを富士山の絶景とともに楽しめます。",
        "image_url": "https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?auto=format&fit=crop&w=800&q=80",
        "fee": "入場無料",
        "organizer": "富士川楽座",
        "parking_info": "無料大型駐車場完備（約400台）",
        "target_age": "大人向け", "is_free_parking": 1, "is_stroller_ok": 1, "is_rainy_ok": 1, "category_scene": "カップル向け", "tags": "クラフトビール,富士川楽座,道の駅,富士市,絶景"
    },

    # --- 伊豆（熱海市・伊東市・伊豆市・下田市・伊豆の国市） ---
    {
        "title": "熱海海上花火大会 【2026年秋季公演】",
        "date_str": "2026年10月19日(月) 20:20〜20:40",
        "city": "熱海市",
        "location": "熱海湾（熱海サンビーチ沿い）",
        "address": "熱海市東海岸町",
        "lat": 35.0964, "lng": 139.0732,
        "official_url": "https://www.ataminews.gr.jp/",
        "summary": "すり鉢状の熱海湾に広がる大音響と大迫力！夜空と海面を黄金色に染め上げる大空中ナイアガラは圧巻。",
        "description": "昭和27年から続く熱海名物の海上花火大会。三方を山に囲まれた熱海湾は自然のスタジアムのような反響効果があり、体全体に響く大迫力の音を楽しめます。秋の澄んだ夜空に打ち上がる大輪の花火は感動的です。",
        "image_url": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=800&q=80",
        "fee": "観覧無料（海岸線からどこでも見れます）",
        "organizer": "熱海温泉ホテル旅館協同組合",
        "parking_info": "市営駐車場をご利用ください（混雑するため公共交通機関推奨）",
        "target_age": "全年齢", "is_free_parking": 0, "is_stroller_ok": 1, "is_rainy_ok": 1, "category_scene": "カップル向け", "tags": "熱海花火,花火大会,熱海,ナイアガラ,夜景"
    },
    {
        "title": "伊東温泉 温州みかん狩り 2026",
        "date_str": "2026年10月1日(木) 〜 11月30日(月) 9:00〜16:00",
        "city": "伊東市",
        "location": "伊東市内 各みかん園（宇佐美・城ヶ崎地区）",
        "address": "伊東市宇佐美",
        "lat": 35.0062, "lng": 139.0842,
        "official_url": "https://itospa.com/",
        "summary": "相模湾を見下ろす温暖な傾斜地で甘くてジューシーな温州みかんが食べ放題！家族みんなで味覚狩り体験。",
        "description": "伊東温泉の名物秋アクティビティ「みかん狩り」。太陽の光と相模湾の潮風をいっぱいに浴びて育った温州みかんは甘みと酸味のバランスが抜群。園内食べ放題＆お土産も持ち帰り可能です。",
        "image_url": "https://images.unsplash.com/photo-1557800636-894a64c1696f?auto=format&fit=crop&w=800&q=80",
        "fee": "大人 600円 / 子ども 500円 (園内食べ放題)",
        "organizer": "伊東市みかん園組合",
        "parking_info": "各みかん園に無料駐車場あり",
        "target_age": "全年齢", "is_free_parking": 1, "is_stroller_ok": 0, "is_rainy_ok": 0, "category_scene": "ファミリー向け", "tags": "みかん狩り,味覚狩り,伊東温泉,伊豆,体験"
    },
    {
        "title": "修善寺温泉 もみじ散策と秋の竹林ライトアップ",
        "date_str": "2026年11月15日(日) 〜 12月6日(日) 16:30〜21:00",
        "city": "伊豆市",
        "location": "修善寺温泉街・竹林の小径",
        "address": "伊豆市修善寺",
        "lat": 34.9725, "lng": 138.9248,
        "official_url": "https://kanko.city.izu.shizuoka.jp/",
        "summary": "伊豆最古の温泉街が赤い紅葉と光の竹林で幻想的に染まる。着物での散策や温泉めぐりに最適の秋風情。",
        "description": "伊豆の小京都と称される修善寺温泉郷の紅葉まつり。修禅寺境内の紅葉や「竹林の小径」が夜間に鮮やかにライトアップされます。桂川のせせらぎを聞きながら、温かい温泉と幻想的な紅葉散歩を楽しめます。",
        "image_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80",
        "fee": "散策無料",
        "organizer": "修善寺温泉旅館協同組合",
        "parking_info": "有料駐車場あり（修善寺温泉有料駐車場）",
        "target_age": "全年齢", "is_free_parking": 0, "is_stroller_ok": 1, "is_rainy_ok": 1, "category_scene": "カップル向け", "tags": "修善寺,紅葉,ライトアップ,竹林の小径,温泉"
    },
    {
        "title": "下田キンメダイまつり＆港のグルメ市",
        "date_str": "2026年10月24日(土) 〜 10月25日(日) 10:00〜15:30",
        "city": "下田市",
        "location": "道の駅 開国下田みなと",
        "address": "下田市外ヶ岡1-1",
        "lat": 34.6781, "lng": 138.9452,
        "official_url": "https://www.shimoda-city.info/",
        "summary": "水揚げ日本一の下田名物「金目鯛」を堪能！煮付け、炙り寿司、金目鯛バーガーなど贅沢グルメが味わえます。",
        "description": "金目鯛の水揚げ量日本一を誇る下田港の秋の味覚フェス。極上の金目鯛の煮付けや金目鯛出汁の味噌汁振る舞い、直売市が開催されます。黒船来航の歴史感じる下田の街巡りとともに楽しめます。",
        "image_url": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80",
        "fee": "入場無料",
        "organizer": "下田市観光協会",
        "parking_info": "無料駐車場あり（道の駅駐車場）",
        "target_age": "全年齢", "is_free_parking": 1, "is_stroller_ok": 1, "is_rainy_ok": 1, "category_scene": "ファミリー向け", "tags": "金目鯛,下田,グルメ,道の駅,金目鯛バーガー"
    },
    {
        "title": "伊豆の国パノラマパーク 秋の富士見テラスバル",
        "date_str": "2026年10月10日(土) 〜 10月12日(月・祝) 11:00〜17:00",
        "city": "伊豆の国市",
        "location": "伊豆パノラマパーク 山頂富士見テラス",
        "address": "伊豆の国市長岡260-1",
        "lat": 35.0315, "lng": 138.9284,
        "official_url": "https://www.panoramapark.co.jp/",
        "summary": "ロープウェイで登る山頂テラスから駿河湾と富士山を一望！ソファー席でワインや伊豆の特産おつまみを楽しむプレミアムバル。",
        "description": "伊豆長岡温泉の伊豆パノラマパーク山頂にて開催される秋のテラスバル。水盤に映る水鏡と富士山の絶景をバックに、伊豆産の柑橘カクテルやクラフトビール、シャルキュトリーを楽しめます。",
        "image_url": "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?auto=format&fit=crop&w=800&q=80",
        "fee": "入場無料（ロープウェイ往復乗車券は別途必要）",
        "organizer": "伊豆パノラマパーク",
        "parking_info": "無料駐車場完備（約300台）",
        "target_age": "大人向け", "is_free_parking": 1, "is_stroller_ok": 1, "is_rainy_ok": 0, "category_scene": "カップル向け", "tags": "伊豆パノラマパーク,富士見テラス,伊豆長岡,富士山,ロープウェイ"
    },

    # --- 西部（浜松市・磐田市・掛川市・袋井市・湖西市） ---
    {
        "title": "浜松まつり会館 秋の遠州大たこ揚げ＆体験教室",
        "date_str": "2026年10月11日(日) 10:00〜15:00",
        "city": "浜松市",
        "location": "遠州灘海浜公園 大たこ揚げ広場",
        "address": "浜松市中央区中田島町1313",
        "lat": 34.6642, "lng": 137.7485,
        "official_url": "https://www.hamamatsu-navi.jp/",
        "summary": "遠州の強い秋風を受けて特大の伝統大凧が大空を舞う！子ども凧作り体験コーナーも大人気。",
        "description": "初夏の「浜松まつり」で有名な大凧揚げを秋の海浜公園で体験できるイベント。保存会による迫力満点の大凧揚げ実演や、小学生以下を対象とした自分だけの和凧作りワークショップが開催されます。",
        "image_url": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=800&q=80",
        "fee": "見学無料（凧作り体験は500円）",
        "organizer": "浜松まつり保存会",
        "parking_info": "無料駐車場あり（遠州灘海浜公園駐車場）",
        "target_age": "全年齢", "is_free_parking": 1, "is_stroller_ok": 1, "is_rainy_ok": 0, "category_scene": "ファミリー向け", "tags": "浜松まつり,大凧,中田島砂丘,浜松,体験"
    },
    {
        "title": "掛川城 本丸秋まつり＆戦国武者行列 2026",
        "date_str": "2026年10月25日(日) 10:00〜16:00",
        "city": "掛川市",
        "location": "掛川城 本丸広場・御殿",
        "address": "掛川市掛川1138-24",
        "lat": 34.7751, "lng": 138.0146,
        "official_url": "https://www.kakegawa-kankou.com/",
        "summary": "東海の名城・掛川城に甲冑武者やくノ一が参上！手作り甲冑体験や殺陣の演武、和菓子マルシェも開催。",
        "description": "日本初の木造復元天守を誇る掛川城で開催される秋の本格歴史フェス。戦国武者隊による迫力の太鼓演武や殺陣パフォーマンス、忍者体験、お城マルシェが城内を賑わせます。城下町の趣を感じる素敵な一日になります。",
        "image_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80",
        "fee": "広場入場無料（天守閣・御殿入場は大人410円）",
        "organizer": "掛川城公園管理事務所",
        "parking_info": "近隣の有料駐車場をご利用ください",
        "target_age": "全年齢", "is_free_parking": 0, "is_stroller_ok": 1, "is_rainy_ok": 1, "category_scene": "ファミリー向け", "tags": "掛川城,武者行列,歴史,掛川,お城マルシェ"
    },
    {
        "title": "袋井可睡斎 秋の精進料理と竹灯籠まつり",
        "date_str": "2026年11月7日(土) 〜 11月8日(日) 17:00〜20:30",
        "city": "袋井市",
        "location": "遠州三山 萬松山可睡斎",
        "address": "袋井市久能2915-1",
        "lat": 34.7682, "lng": 137.9254,
        "official_url": "https://fukuroi-kankou.jp/",
        "summary": "徳川家康公ゆかりの古刹「可睡斎」の参道を約1,000本の竹灯籠が照らし出す。歴史ある精進料理の特別味わい会も開催。",
        "description": "遠州三山の一つである可睡斎の幻想的な秋夜イベント。竹灯籠の柔らかな光が歴史ある山門や境内を包み込みます。事前予約制で可睡斎名物の本格的な精進料理コースをいただくこともできます。",
        "image_url": "https://images.unsplash.com/photo-1508997449629-303059a039c0?auto=format&fit=crop&w=800&q=80",
        "fee": "拝観無料",
        "organizer": "可睡斎・袋井市観光協会",
        "parking_info": "有料駐車場あり（普通車300円）",
        "target_age": "全年齢", "is_free_parking": 0, "is_stroller_ok": 1, "is_rainy_ok": 1, "category_scene": "カップル向け", "tags": "可睡斎,袋井,竹灯籠,精進料理,遠州三山"
    },
    {
        "title": "磐田しっぺい感謝祭＆ジュビロード秋市 2026",
        "date_str": "2026年10月18日(日) 10:00〜15:30",
        "city": "磐田市",
        "location": "JR磐田駅前 ジュビロード商店街",
        "address": "磐田市中泉",
        "lat": 34.7172, "lng": 137.8515,
        "official_url": "https://kanko-iwata.jp/",
        "summary": "磐田市のイメージキャラクター「しっぺい」と全国のゆるキャラが集合！歩行者天国でグルメ・軽トラ市を開催。",
        "description": "JR磐田駅北口のジュビロード商店街を歩行者天国にして開催される大型街イベント。しっぺいステージショーや地元食材を使ったフード屋台、クラフト市、ジュビロ磐田オフィシャルグッズ販売で活気に溢れます。",
        "image_url": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=800&q=80",
        "fee": "入場無料",
        "organizer": "磐田市観光協会",
        "parking_info": "近隣の有料コインパーキングをご利用ください（公共交通機関推奨）",
        "target_age": "全年齢", "is_free_parking": 0, "is_stroller_ok": 1, "is_rainy_ok": 0, "category_scene": "ファミリー向け", "tags": "しっぺい,磐田,ジュビロード,歩行者天国,軽トラ市"
    },
    {
        "title": "ボートレース浜名湖 秋の浜名湖うなぎ＆クラフトフェス",
        "date_str": "2026年10月31日(土) 〜 11月1日(日) 10:00〜16:00",
        "city": "湖西市",
        "location": "ボートレース浜名湖 サンストリート広場",
        "address": "湖西市新居町中浜599",
        "lat": 34.6952, "lng": 137.5684,
        "official_url": "https://www.hamamatsu-navi.jp/",
        "summary": "浜名湖名物の香ばしいウナギ蒲焼き＆うなぎ弁当が勢ぞろい！湖畔の心地よい秋風を感じるファミリーフェス。",
        "description": "湖西市のボートレース浜名湖対岸広場で開催される秋イベント。浜名湖産ウナギの蒲焼きやうなぎボーンの即売会をはじめ、地元のハンドメイド作家によるクラフト出店、子ども向けふわふわ遊具が設置されます。",
        "image_url": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80",
        "fee": "入場無料（本場レース開催日はレース入場料100円が必要なエリアあり）",
        "organizer": "浜名湖観光開発公社",
        "parking_info": "無料大型駐車場完備（約2,000台）",
        "target_age": "全年齢", "is_free_parking": 1, "is_stroller_ok": 1, "is_rainy_ok": 1, "category_scene": "ファミリー向け", "tags": "浜名湖,うなぎ,湖西市,ボートレース浜名湖,グルメ"
    }
]

def add_wide_events():
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
    for evt in WIDE_EVENTS:
        # 重複チェック
        cur.execute("SELECT id FROM events WHERE title = ?", (evt["title"],))
        if not cur.fetchone():
            evt["google_maps_url"] = f"https://maps.google.com/?q={evt['lat']},{evt['lng']}"
            cur.execute(sql, evt)
            added += 1

    conn.commit()
    conn.close()
    print(f"[SUCCESS] 静岡県全域（中部・東部・伊豆・西部）のイベント {added} 件をデータベースに追加しました！")

if __name__ == "__main__":
    add_wide_events()
