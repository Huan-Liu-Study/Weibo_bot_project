# -*- coding: utf-8 -*-
"""
label_service.py — 数据标注服务层 (v3.0)
=========================================
为 Web 前端提供标注队列获取、标注结果提交、标注进度查询等功能。
数据来源：topic_cache.db（话题检测历史）
数据存储：label_store.db + golden_testset_labeled.csv（双写）
"""

import sqlite3
import json
import os
import pandas as pd
from datetime import datetime

from scoring import FEATURE_COLS, get_model_proba, compute_final_score, is_official_media
import topic_db

# ===================== 数据库初始化 =====================

LABEL_DB_PATH = os.path.join(os.path.dirname(__file__), 'label_store.db')

def _get_label_conn():
    conn = sqlite3.connect(LABEL_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_label_db():
    conn = _get_label_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS labeled_users (
            user_id       TEXT PRIMARY KEY,
            screen_name   TEXT,
            topic         TEXT,
            suspicion_label INTEGER,
            suspicion_score REAL,
            ai_pred_score REAL,
            labeled_at    TEXT,
            features_json TEXT,
            trained       INTEGER DEFAULT 0
        );
    """)
    # 兼容旧数据库：如果表已存在但缺少 trained 列，则追加
    try:
        conn.execute("ALTER TABLE labeled_users ADD COLUMN trained INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass  # 列已存在，忽略
    conn.close()

init_label_db()

# ===================== 核心函数 =====================

def get_label_queue(topic=None, page=1, page_size=20):
    """
    从 topic_cache.db 中获取尚未标注的用户列表。
    按 AI 预判分从高到低排序（优先标注最可疑的）。
    """
    # 1. 获取已标注的 user_id 集合
    conn = _get_label_conn()
    rows = conn.execute("SELECT user_id FROM labeled_users").fetchall()
    conn.close()
    labeled_ids = {r[0] for r in rows}

    # 2. 从 topic_cache.db 获取所有帖子
    topics_list = topic_db.get_all_topics()
    if not topics_list:
        return {'users': [], 'total': 0, 'page': page, 'labeled_count': len(labeled_ids)}

    all_users = {}  # uid -> user_data dict

    target_topics = [topic] if topic else [t['topic'] for t in topics_list]

    for t in target_topics:
        df = topic_db.load_all_posts(t)
        if df.empty:
            continue
        for _, row in df.iterrows():
            uid = str(row.get('user_id', ''))
            if not uid or uid in labeled_ids or uid in all_users:
                continue
            all_users[uid] = {
                'user_id': uid,
                'screen_name': str(row.get('用户昵称', '')),
                'topic': t,
                'followers_count': int(row.get('followers_count', 0)),
                'friends_count': int(row.get('friends_count', 0)),
                'statuses_count': int(row.get('statuses_count', 0)),
                'avatar_hd': str(row.get('avatar_hd', '')),
                'description': str(row.get('description', ''))[:100],
                'verified_reason': str(row.get('verified_reason', '')),
                'ai_pred_score': float(row.get('bot_probability', row.get('suspicion_score', 0.5))),
                'text_preview': str(row.get('微博正文', ''))[:150],
                'features': {c: float(row.get(c, 0)) for c in FEATURE_COLS},
                'is_official_media': int(row.get('is_official_media', 0))
            }

    # 3. 排序：AI 预判分从高到低（优先标注最可疑的）
    users_list = sorted(all_users.values(), key=lambda x: x['ai_pred_score'], reverse=True)
    total = len(users_list)

    # 4. 分页
    start = (page - 1) * page_size
    end = start + page_size
    page_users = users_list[start:end]

    return {
        'users': page_users,
        'total': total,
        'page': page,
        'page_size': page_size,
        'labeled_count': len(labeled_ids),
        'topics': [t['topic'] for t in topics_list]
    }


def submit_label(user_id, label, topic='', ai_pred_score=0.5, features=None, screen_name=''):
    """
    提交标注结果，双写到 label_store.db 和 golden_testset_labeled.csv。
    label: 0-4 的整数档位，-1 = 新闻媒体（排除，不进入训练数据）
    """
    is_media_exclude = (label == -1)
    score = 0.0 if is_media_exclude else round(label / 4.0, 4)
    now = datetime.now().isoformat()
    features_json = json.dumps(features or {}, ensure_ascii=False)

    # 如果前端没传 screen_name，尝试从 topic_cache.db 查找
    if not screen_name:
        try:
            tc = topic_db._get_conn()
            rows = tc.execute("SELECT data_json FROM topic_posts").fetchall()
            tc.close()
            for row in rows:
                data = json.loads(row[0])
                if str(data.get('user_id', '')) == str(user_id):
                    screen_name = str(data.get('用户昵称', ''))
                    break
        except:
            pass

    # 1. 写入 SQLite
    conn = _get_label_conn()

    conn.execute("""
        INSERT OR REPLACE INTO labeled_users 
        (user_id, screen_name, topic, suspicion_label, suspicion_score, ai_pred_score, labeled_at, features_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (str(user_id), screen_name, topic, label, score, ai_pred_score, now, features_json))
    conn.commit()
    conn.close()

    # 如果是媒体排除标记，直接自动加入媒体白名单大模型
    if is_media_exclude:
        import media_db
        media_db.add_media_account(user_id, screen_name)


    # 2. 同步追加到 golden_testset_labeled.csv（媒体排除不写入训练库）
    if not is_media_exclude:
        golden_file = os.path.join(os.path.dirname(__file__), 'golden_testset_labeled.csv')
        row_data = {
            'user_id': user_id,
            '用户昵称': screen_name,
            'topic_query': topic,
            'suspicion_label': label,
            'suspicion_score': score,
        }
        if features:
            row_data.update(features)

        new_df = pd.DataFrame([row_data])
        if os.path.exists(golden_file):
            try:
                old_df = pd.read_csv(golden_file, encoding='utf-8-sig')
                old_df = old_df[old_df['user_id'].astype(str) != str(user_id)]
                final_df = pd.concat([old_df, new_df], ignore_index=True)
            except:
                final_df = new_df
        else:
            final_df = new_df

        final_df.to_csv(golden_file, index=False, encoding='utf-8-sig')

    return {'status': 'success', 'user_id': user_id, 'label': label, 'score': score}


def get_label_stats():
    """获取标注进度统计"""
    conn = _get_label_conn()
    total = conn.execute("SELECT COUNT(*) FROM labeled_users WHERE trained = 0").fetchone()[0]
    dist = conn.execute(
        "SELECT suspicion_label, COUNT(*) FROM labeled_users WHERE trained = 0 GROUP BY suspicion_label ORDER BY suspicion_label"
    ).fetchall()
    recent = conn.execute(
        "SELECT user_id, screen_name, suspicion_label, labeled_at FROM labeled_users WHERE trained = 0 ORDER BY labeled_at DESC LIMIT 5"
    ).fetchall()
    conn.close()

    label_names = {-1: '新闻媒体(排除)', 0: '确定真人', 1: '大概率真人', 2: '不确定', 3: '比较可疑', 4: '几乎确定水军'}
    distribution = {label_names.get(r[0], str(r[0])): r[1] for r in dist}
    recent_list = [{'user_id': r[0], 'screen_name': r[1], 'label': r[2], 'labeled_at': r[3]} for r in recent]

    return {
        'total_labeled': total,
        'distribution': distribution,
        'recent': recent_list
    }


def get_labeled_queue(topic=None, page=1, page_size=20):
    """
    获取已标注但尚未用于训练的用户列表（trained=0 且有标注记录的）。
    用于前端「已标注」视图。返回的数据会从 topic_cache.db 补充完整的用户信息。
    """
    conn = _get_label_conn()
    base_sql = "FROM labeled_users WHERE trained = 0"
    params = []
    if topic:
        base_sql += " AND topic = ?"
        params.append(topic)

    total = conn.execute(f"SELECT COUNT(*) {base_sql}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT user_id, screen_name, topic, suspicion_label, suspicion_score, "
        f"ai_pred_score, labeled_at, features_json {base_sql} ORDER BY labeled_at DESC LIMIT ? OFFSET ?",
        params + [page_size, (page - 1) * page_size]
    ).fetchall()
    conn.close()

    # 从 topic_cache.db 中建立 uid -> 完整用户信息 的映射
    uid_set = {r[0] for r in rows}
    user_info_map = {}  # uid -> dict with screen_name, followers_count, etc.
    if uid_set:
        try:
            tc = topic_db._get_conn()
            all_posts = tc.execute("SELECT data_json FROM topic_posts").fetchall()
            tc.close()
            for post_row in all_posts:
                data = json.loads(post_row[0])
                uid = str(data.get('user_id', ''))
                if uid in uid_set and uid not in user_info_map:
                    user_info_map[uid] = {
                        'screen_name': str(data.get('用户昵称', '')),
                        'followers_count': int(data.get('followers_count', 0)),
                        'friends_count': int(data.get('friends_count', 0)),
                        'statuses_count': int(data.get('statuses_count', 0)),
                        'avatar_hd': str(data.get('avatar_hd', '')),
                        'description': str(data.get('description', ''))[:100],
                        'verified_reason': str(data.get('verified_reason', '')),
                        'text_preview': str(data.get('微博正文', ''))[:150],
                    }
        except Exception:
            pass

    label_names = {-1: '新闻媒体(排除)', 0: '确定真人', 1: '大概率真人', 2: '不确定', 3: '比较可疑', 4: '几乎确定水军'}
    users = []
    for r in rows:
        features = {}
        try:
            features = json.loads(r[7]) if r[7] else {}
        except Exception:
            pass

        uid = r[0]
        info = user_info_map.get(uid, {})
        # 优先使用 topic_cache 中的 screen_name，如果没有则使用 labeled_users 中的
        screen_name = info.get('screen_name', '') or r[1] or ''

        users.append({
            'user_id': uid,
            'screen_name': screen_name,
            'topic': r[2] or '',
            'suspicion_label': r[3],
            'suspicion_score': r[4],
            'ai_pred_score': r[5] or 0.5,
            'labeled_at': r[6],
            'label_name': label_names.get(r[3], str(r[3])),
            'features': features,
            # 补充的用户元数据
            'followers_count': info.get('followers_count', 0),
            'friends_count': info.get('friends_count', 0),
            'statuses_count': info.get('statuses_count', 0),
            'avatar_hd': info.get('avatar_hd', ''),
            'description': info.get('description', ''),
            'verified_reason': info.get('verified_reason', ''),
            'text_preview': info.get('text_preview', ''),
        })

    return {
        'users': users,
        'total': total,
        'page': page,
        'page_size': page_size
    }


def mark_as_trained():
    """模型训练完成后，将所有 trained=0 的记录标记为 trained=1"""
    conn = _get_label_conn()
    count = conn.execute("UPDATE labeled_users SET trained = 1 WHERE trained = 0").rowcount
    conn.commit()
    conn.close()
    return count

def delete_user(user_id):
    """
    永久删除指定用户的缓存帖子和标注记录。
    """
    # 1. 从缓存库中彻底删除该用户的所有帖子
    topic_db.delete_user_posts(user_id)
    
    # 2. 从已标注库中删除
    conn = _get_label_conn()
    conn.execute("DELETE FROM labeled_users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True
