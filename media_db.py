# -*- coding: utf-8 -*-
"""
media_db.py  —  动态新闻媒体库 (v1.0.0)
=====================================
永久存储被用户或系统确认为“新闻媒体”（label=-1）的账号 UID。
当需要进行话题检测或单用户打分时，首先通过本库进行白名单核验，
如果命中则直接判定为官方媒体（可疑度衰减免死金牌）。
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'media_store.db')

def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS media_accounts (
            user_id TEXT PRIMARY KEY,
            screen_name TEXT,
            added_at TEXT
        );
    """)
    conn.close()

# 每次被引入时自动建表
init_db()

def add_media_account(user_id: str, screen_name: str = ""):
    """
    将账户加入新闻媒体白名单。
    如果已经存在则忽略（IGNORE）。
    """
    try:
        conn = _get_conn()
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT OR IGNORE INTO media_accounts (user_id, screen_name, added_at) VALUES (?, ?, ?)",
            (str(user_id), str(screen_name), now)
        )
        conn.commit()
    except Exception as e:
        print(f"Error adding to media db: {e}")
    finally:
        conn.close()

def is_in_media_db(user_id: str) -> bool:
    """
    查询某个账号是否在我们的媒体白名单中。
    """
    try:
        conn = _get_conn()
        row = conn.execute("SELECT 1 FROM media_accounts WHERE user_id = ?", (str(user_id),)).fetchone()
        return bool(row)
    except Exception as e:
        print(f"Error reading media db: {e}")
        return False
    finally:
        try:
            conn.close()
        except:
            pass
    return False

def get_all_media() -> list:
    """
    获取全部存入库中的新闻媒体账号
    """
    try:
        conn = _get_conn()
        rows = conn.execute("SELECT user_id, screen_name, added_at FROM media_accounts ORDER BY added_at DESC").fetchall()
        return [{"user_id": r[0], "screen_name": r[1], "added_at": r[2]} for r in rows]
    except Exception as e:
        print(f"Error reading all media db: {e}")
        return []
    finally:
        try:
            conn.close()
        except:
            pass
    return []

def delete_media_account(user_id: str) -> bool:
    """
    从白名单中删除指定媒体账号
    """
    try:
        conn = _get_conn()
        conn.execute("DELETE FROM media_accounts WHERE user_id = ?", (str(user_id),))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting from media db: {e}")
        return False
    finally:
        try:
            conn.close()
        except:
            pass
    return False
