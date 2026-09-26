# -*- coding: utf-8 -*-
"""
Database Audit & Cleanup Script for Shizuoka Event Navi
(audit_and_cleanup_events.py)
Audits existing events in events.db to detect and remove hallucinated,
non-existent, or inaccurate events.
"""

import sqlite3
import os
import sys
import logging
import ai_rewriter
import generate_site

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cleanup")

DB_PATH = "events.db"

# List of known synthetic/estimated item IDs from seed data that require cleanup
SYNTHETIC_IDS_TO_REMOVE = {
    831, 833, 834, 835, 837, 838, 839, 844, 845, 849, 850, 851, 852, 853, 854
}

def audit_and_clean():
    if not os.path.exists(DB_PATH):
        logger.error("events.db が見つかりません。")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT id, title, city, date_str, official_url FROM events WHERE item_type = 'event'")
    rows = cur.fetchall()
    logger.info(f"総イベント数: {len(rows)} 件の検証を開始します...")

    removed_count = 0
    api_key = os.environ.get("GEMINI_API_KEY")

    for item_id, title, city, date_str, official_url in rows:
        should_remove = False

        # 1. 既知の人工推定データを特定して削除
        if item_id in SYNTHETIC_IDS_TO_REMOVE:
            should_remove = True
            logger.info(f"[手動検出削除] ID {item_id}: {title} (推測データのため削除)")

        # 2. GEMINI_API_KEY が設定されている場合は Google Search Grounding で検証
        elif api_key:
            res = ai_rewriter.verify_and_rewrite_event(raw_title=title, city=city or "静岡県")
            if not res.get("is_verified", True):
                should_remove = True
                logger.info(f"[AI検証削除] ID {item_id}: {title} (Google検索で実在確認できず削除)")

        if should_remove:
            cur.execute("DELETE FROM events WHERE id = ?", (item_id,))
            removed_count += 1

    conn.commit()
    conn.close()

    logger.info(f"精査完了: 合計 {removed_count} 件の未検証・不正確なイベントを削除しました。")

    # サイトの再生成
    logger.info("Webサイト (dist/index.html) を最新データで再生成します...")
    generate_site.generate_site()

if __name__ == "__main__":
    audit_and_clean()
