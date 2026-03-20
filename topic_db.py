"""
topic_db.py  —  SQLite persistence layer for incremental topic crawling (v1.7.0)
Manages topic_cache.db with two tables: topic_meta and topic_posts.
"""
import sqlite3
import json
import os
import pandas as pd
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'topic_cache.db')


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS topic_meta (
            topic         TEXT PRIMARY KEY,
            total_fetched INTEGER DEFAULT 0,
            last_updated  TEXT
        );
        CREATE TABLE IF NOT EXISTS topic_posts (
            id      TEXT,
            topic   TEXT,
            data_json TEXT,
            PRIMARY KEY (id, topic)
        );
    """)
    conn.close()


def get_existing_ids(topic: str) -> set:
    """Return the set of weibo IDs already stored for a topic."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id FROM topic_posts WHERE topic = ?", (topic,)
    ).fetchall()
    conn.close()
    return {r[0] for r in rows}


def save_posts(topic: str, df: pd.DataFrame):
    """Append new rows into topic_posts and update topic_meta."""
    if df.empty:
        return

    conn = _get_conn()
    cur = conn.cursor()

    # Convert each row to a JSON string for storage
    records = []
    for _, row in df.iterrows():
        row_dict = {}
        for k, v in row.items():
            # Make everything JSON-serializable
            if pd.isna(v) if not isinstance(v, (list, dict)) else False:
                row_dict[k] = None
            elif hasattr(v, 'item'):          # numpy scalar
                row_dict[k] = v.item()
            elif hasattr(v, 'isoformat'):     # datetime
                row_dict[k] = str(v)
            else:
                row_dict[k] = v
        mid = str(row_dict.get('id', ''))
        records.append((mid, topic, json.dumps(row_dict, ensure_ascii=False)))

    cur.executemany(
        "INSERT OR REPLACE INTO topic_posts (id, topic, data_json) VALUES (?, ?, ?)",
        records
    )

    # Update meta
    total = cur.execute(
        "SELECT COUNT(*) FROM topic_posts WHERE topic = ?", (topic,)
    ).fetchone()[0]

    cur.execute("""
        INSERT INTO topic_meta (topic, total_fetched, last_updated)
        VALUES (?, ?, ?)
        ON CONFLICT(topic) DO UPDATE SET
            total_fetched = excluded.total_fetched,
            last_updated  = excluded.last_updated
    """, (topic, total, datetime.now().isoformat()))

    conn.commit()
    conn.close()


def load_all_posts(topic: str) -> pd.DataFrame:
    """Load ALL stored posts for a topic as a DataFrame."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT data_json FROM topic_posts WHERE topic = ?", (topic,)
    ).fetchall()
    conn.close()

    if not rows:
        return pd.DataFrame()

    records = [json.loads(r[0]) for r in rows]
    return pd.DataFrame(records)


def get_topic_meta(topic: str) -> dict:
    """Return meta info for a topic."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT total_fetched, last_updated FROM topic_meta WHERE topic = ?",
        (topic,)
    ).fetchone()
    conn.close()

    if row:
        return {'total_fetched': row[0], 'last_updated': row[1]}
    return {'total_fetched': 0, 'last_updated': None}

def get_all_topics() -> list:
    """Return a list of all stored topics and their metadata."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT topic, total_fetched, last_updated FROM topic_meta ORDER BY last_updated DESC"
    ).fetchall()
    conn.close()
    
    topics = []
    for r in rows:
        topics.append({
            'topic': r[0],
            'total_fetched': r[1],
            'last_updated': r[2]
        })
    return topics



def clear_topic(topic: str):
    """Delete all data for a specific topic (fresh start)."""
    conn = _get_conn()
    conn.execute("DELETE FROM topic_posts WHERE topic = ?", (topic,))
    conn.execute("DELETE FROM topic_meta WHERE topic = ?", (topic,))
    conn.commit()
    conn.close()


# Auto-init on import
init_db()
