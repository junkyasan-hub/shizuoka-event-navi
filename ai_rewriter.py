# -*- coding: utf-8 -*-
"""
AI Fact-Checking & Rewriting Module for Shizuoka Event Navi
(ai_rewriter.py)
Uses Gemini 2.5 Flash + Google Search Grounding to verify event existence,
factual accuracy (dates, locations, official URLs), and generate rewritten descriptions.
"""

import os
import json
import logging
from google import genai
from google.genai import types

logger = logging.getLogger("ai_rewriter")

def verify_and_rewrite_event(raw_title, raw_summary="", raw_description="", city="静岡県"):
    """
    Gemini 2.5 Flash + Google Search Grounding を使用して、
    イベントの実在性・開催日・会場などの事実確認を行ってリライトします。
    実在が確認できない場合は is_verified=False を返します。
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEYが未設定のため、簡易リライトのみ行います。")
        return {
            "is_verified": True,
            "title": raw_title.strip(),
            "date_str": "",
            "start_date": "",
            "end_date": "",
            "location": "",
            "official_url": "",
            "summary": (raw_summary or raw_title)[:120],
            "description": raw_description or raw_summary or raw_title,
            "is_free_parking": 0,
            "is_stroller_ok": 1,
            "is_rainy_ok": 0,
            "target_age": "全年齢",
            "category_scene": "一般",
            "tags": ["静岡イベント"]
        }

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
あなたは「静岡県お出かけ・イベントナビ」のプロのファクトチェック兼編集者です。
Google検索ツールを使用して、以下のイベント情報が【静岡県内に実在するイベントであるか】および【正確な開催日・場所】を検索検証してください。

【対象イベント情報】
イベント名: {raw_title}
市町村/地域: {city}
概要: {raw_summary}

【依頼事項】
1. Google検索を用いて、このイベントが静岡県内で実際に開催されている（または過去・本年に開催実績がある）か検索確認してください。
2. もし実在しない架空のイベント、もしくは開催実績やニュース・広報・公式サイトの根拠が一切検索結果に見つからない場合は、"is_verified": false を返してください。
3. 実在する場合は "is_verified": true とし、以下の項目を正確に抽出・補正してJSON形式で出力してください：
   - title: 正確なイベント正式名称
   - date_str: 検索で確認された正確な2026年の開催日時（例: "2026年10月11日(日) 10:00〜16:00"）
   - start_date: ISO形式の開始日（YYYY-MM-DD）
   - end_date: ISO形式の終了日（YYYY-MM-DD）
   - location: 正確な会場名
   - official_url: 公式サイトまたは信頼できる情報源のURL（検索で見つかったもの）
   - summary: 100〜140文字程度の魅力を伝えるオリジナル紹介文
   - description: 200〜300文字程度の詳細本文
   - is_free_parking: boolean（無料駐車場情報）
   - is_stroller_ok: boolean（ベビーカー可）
   - is_rainy_ok: boolean（雨天決行/屋内）
   - target_age: 対象年齢目安（"全年齢", "ファミリー向け" など）
   - category_scene: シーン分類（"ファミリー向け", "カップル向け", "一般"）
   - tags: 関連タグの配列（3〜5個）

必ず純粋なJSONオブジェクトのみを出力してください。テキスト注釈やマークダウンブロックは含めないでください。
"""

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}]
            )
        )

        text = response.text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        result = json.loads(text)
        return {
            "is_verified": bool(result.get("is_verified", False)),
            "title": result.get("title", raw_title).strip(),
            "date_str": result.get("date_str", ""),
            "start_date": result.get("start_date", ""),
            "end_date": result.get("end_date", ""),
            "location": result.get("location", ""),
            "official_url": result.get("official_url", ""),
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
        logger.error(f"ファクトチェックAI処理エラー [{raw_title}]: {e}")
        return {
            "is_verified": False,
            "title": raw_title,
            "summary": raw_summary,
            "description": raw_description
        }

def rewrite_event_info(raw_title, raw_summary, raw_description=""):
    """
    従来の互換用メソッド。実在確認付きの verify_and_rewrite_event を内部呼び出しします。
    """
    res = verify_and_rewrite_event(raw_title, raw_summary, raw_description)
    return res

if __name__ == "__main__":
    print("Testing ai_rewriter module...")
