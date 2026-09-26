import os
import json
import logging
from google import genai
from google.genai import types

logger = logging.getLogger("ai_rewriter")

def rewrite_event_info(raw_title, raw_summary, raw_description=""):
    """
    Gemini API (gemini-2.5-flash) を使用して、クローリングした生テキストを独自リライト＆タグ付けする。
    GEMINI_API_KEY が未設定の場合は、フォールバック（簡易整形）して返します。
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    
    # APIキーが無い場合の安全なフォールバック
    if not api_key:
        logger.warning("GEMINI_API_KEYが未設定のため、AIリライトをスキップしてフォールバック処理を行います。")
        return {
            "title": raw_title.strip(),
            "summary": (raw_summary or raw_title)[:120],
            "description": raw_description or raw_summary or raw_title,
            "is_free_parking": 0,
            "is_stroller_ok": 1,
            "is_rainy_ok": 0,
            "target_age": "全年齢",
            "category_scene": "一般",
            "tags": ["静岡イベント", "お出かけ"]
        }

    try:
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
あなたは観光・イベントメディア「静岡県お出かけ・イベントナビ」のプロの編集者です。
収集された以下のイベント情報を読み込み、著作権や規約に配慮してオリジナルな言葉遣いにリライトし、属性タグを判定してください。

【元データ】
タイトル: {raw_title}
概要: {raw_summary}
詳細本文: {raw_description}

【要求】
1. タイトル: 魅力的で簡潔な表記（元のタイトルをベースに読みやすく整理）
2. summary: カード一覧用の要約文（100〜140文字程度。魅力を伝えるオリジナルの紹介文）
3. description: 詳細ページ用の本文（200〜300文字程度。見どころや特徴をオリジナル文章でまとめる）
4. is_free_parking: 駐車場無料の情報があれば true、無ければ false
5. is_stroller_ok: ベビーカー可/子連れ向けなら true、不確定または不可なら false
6. is_rainy_ok: 屋内イベントや雨天決行なら true、屋外で雨天中止等なら false
7. target_age: 対象年齢の目安（例: "全年齢", "未就学児〜小学生", "大人向け" など）
8. category_scene: 一番適するシーン（"ファミリー向け", "カップル向け", "一般" のいずれか1つ）
9. tags: 関連するキーワードタグの配列（3〜5個。例: ["ファミリー", "屋台", "体験イベント"]）

必ず以下のJSONオブジェクト形式のみで返答してください。
"""

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        result = json.loads(response.text)
        
        return {
            "title": result.get("title", raw_title).strip(),
            "summary": result.get("summary", raw_summary).strip(),
            "description": result.get("description", raw_description).strip(),
            "is_free_parking": 1 if result.get("is_free_parking") else 0,
            "is_stroller_ok": 1 if result.get("is_stroller_ok") else 0,
            "is_rainy_ok": 1 if result.get("is_rainy_ok") else 0,
            "target_age": result.get("target_age", "全年齢"),
            "category_scene": result.get("category_scene", "一般"),
            "tags": result.get("tags", ["静岡イベント"])
        }
        
    except Exception as e:
        logger.error(f"AIリライト中にエラーが発生しました: {e}")
        return {
            "title": raw_title.strip(),
            "summary": (raw_summary or raw_title)[:120],
            "description": raw_description or raw_summary or raw_title,
            "is_free_parking": 0,
            "is_stroller_ok": 1,
            "is_rainy_ok": 0,
            "target_age": "全年齢",
            "category_scene": "一般",
            "tags": ["静岡イベント"]
        }

if __name__ == "__main__":
    # テスト実行
    test_res = rewrite_event_info(
        "駿府城公園 秋のクラフト市",
        "静岡市葵区の駿府城公園でハンドメイド作品やグルメ屋台が集う秋のクラフト市が開催されます。駐車場は近隣をご利用ください。ベビーカーでの入場もスムーズです。"
    )
    print("AI Rewrite Result Sample:")
    print(json.dumps(test_res, ensure_ascii=False, indent=2))
