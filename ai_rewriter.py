# -*- coding: utf-8 -*-
"""
AI Fact-Checking, Rewriting & Regional Event Discovery Module for Shizuoka Event Navi
(ai_rewriter.py)
Uses Gemini 3.5 Flash-lite + Google Search Grounding to verify event existence,
discover regional official events across Shizuoka prefecture, and generate clean structured data.
"""

import os
import json
import logging
from google import genai
from google.genai import types

logger = logging.getLogger("ai_rewriter")

def verify_and_rewrite_event(raw_title, raw_summary="", raw_description="", city="静岡県"):
    """
    Gemini 3.5 Flash-lite + Google Search Grounding を使用して、
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

        model_candidates = ['gemini-3.5-flash-lite', 'gemini-3.5-flash', 'gemini-2.5-flash']
        response = None
        for model_name in model_candidates:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        tools=[{"google_search": {}}]
                    )
                )
                if response:
                    break
            except Exception as em:
                logger.warning(f"モデル [{model_name}] での呼び出し失敗、次候補を試行します: {em}")

        if not response:
            raise RuntimeError("すべてのモデル候補での呼び出しに失敗しました。")

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

def discover_regional_events(region_name, cities, exclude_titles=None):
    """
    Gemini 3.5 Flash-lite + Google Search Grounding を使用して、
    指定地域の2026年最新公的・観光イベント情報を自動探索・抽出します。
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning(f"[{region_name}] GEMINI_API_KEYが未設定のため地域探索をスキップします。")
        return []

    try:
        client = genai.Client(api_key=api_key)
        cities_str = "、".join(cities)
        # 登録済みの最新50件および主要タイトルを除外対象として提示
        recent_titles = list(exclude_titles)[-50:] if exclude_titles else []
        exclude_str = "、".join(recent_titles) if recent_titles else "なし"

        prompt = f"""
あなたは「静岡県お出かけ・イベントナビ」のプロのイベント編集者です。
Google検索ツールを使用して、静岡県の【{region_name}（対象自治体: {cities_str}）】で2026年9月〜12月に開催される最新の観光イベント、季節の祭り、マルシェ、クラフト市、秋の体験・ライトアップ、地域行事の情報を3〜5件検索し、正確な開催情報を抽出してください。

【重要：除外条件】
以下のイベントは既に登録済みのため、これら以外の【まだ登録されていない新しい地域イベント】を具体的に検索して抽出してください：
{exclude_str}

【検索対象の条件】
- 地域: {cities_str} のいずれかの市町
- 開催時期: 2026年9月〜12月（現在開催中または今後開催予定のもの）
- 情報源: 市役所公式、観光協会、公的ニュース等の信頼できる発表情報

【返答フォーマット】
以下のJSON構造の配列形式のみで返してください（解説文やマークダウンブロックは含めないでください）：
[
  {{
    "title": "正確なイベント正式名称",
    "city": "市町村名（例: 静岡市、沼津市等）",
    "date_str": "正確な2026年の開催日時（例: 2026年10月15日(土)〜10月16日(日)）",
    "location": "会場名",
    "address": "住所",
    "official_url": "公式サイトまたは情報源のURL",
    "summary": "100〜140文字程度の魅力が伝わるオリジナルの紹介文",
    "description": "200〜300文字程度の詳細本文",
    "fee": "料金情報",
    "organizer": "主催者名",
    "parking_info": "駐車場情報",
    "is_free_parking": true,
    "is_stroller_ok": true,
    "is_rainy_ok": false,
    "target_age": "対象年齢（例: 全年齢, ファミリー向け）",
    "category_scene": "シーン分類（ファミリー向け, カップル向け, 一般 のいずれか）",
    "tags": ["関連タグ1", "関連タグ2", "関連タグ3"]
  }}
]
"""

        model_candidates = ['gemini-3.5-flash-lite', 'gemini-3.5-flash', 'gemini-2.5-flash']
        response = None
        for model_name in model_candidates:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        tools=[{"google_search": {}}]
                    )
                )
                if response:
                    break
            except Exception as em:
                logger.warning(f"モデル [{model_name}] 地域探索失敗: {em}")

        if not response:
            return []

        text = response.text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        items = json.loads(text)
        if isinstance(items, list):
            return items
        return []

    except Exception as e:
        logger.error(f"地域イベント自動探索エラー [{region_name}]: {e}")
        return []

def rewrite_event_info(raw_title, raw_summary, raw_description=""):
    res = verify_and_rewrite_event(raw_title, raw_summary, raw_description)
    return res

if __name__ == "__main__":
    print("Testing ai_rewriter module...")
