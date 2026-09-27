# -*- coding: utf-8 -*-
"""
Database Audit & Cleanup Script for Shizuoka Event Navi
(audit_and_cleanup_events.py)
Audits existing events in events.db to detect and remove specific synthetic/unverified items.
"""

import sqlite3
import os
import logging
import generate_site

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cleanup")

DB_PATH = "events.db"

# 削除対象の特定の仮登録・推測データIDリストのみ
SYNTHETIC_IDS_TO_REMOVE = {
    831, 833, 834, 835, 837, 838, 839, 844, 845, 849, 850, 851, 852, 853, 854
}

def audit_and_clean():
    if not os.path.exists(DB_PATH):
        logger.error("events.db が見つかりません。")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT id, title FROM events WHERE item_type = 'event'")
    rows = cur.fetchall()
    logger.info(f"DB内イベント総数: {len(rows)} 件")

    removed_count = 0
    for item_id, title in rows:
        if item_id in SYNTHETIC_IDS_TO_REMOVE:
            cur.execute("DELETE FROM events WHERE id = ?", (item_id,))
            removed_count += 1
            logger.info(f"[手動特定削除] ID {item_id}: {title}")

    conn.commit()
    conn.close()

    logger.info(f"精査完了: 合計 {removed_count} 件の特定推測イベントを削除しました。")

    # サイトの再生成
    logger.info("Webサイト (dist/index.html) を最新データで再生成します...")
    generate_site.generate_site()

if __name__ == "__main__":
    audit_and_clean()
