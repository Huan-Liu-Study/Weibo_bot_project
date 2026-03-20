import pandas as pd
import numpy as np

import subprocess
import time
import requests
import joblib
import os
import re
import sys
import asyncio
import aiohttp
# SnowNLP is lazy-loaded inside get_sentiment() to avoid MemoryError
# when Flask debug reloader double-imports this module
from datetime import datetime
import topic_db


def _load_cookie_from_settings():
    """从 weibo-search/weibo/settings.py 中动态读取 Cookie，统一管理"""
    from config import load_cookie
    return load_cookie()

from weibo_api import fetch_all_users_info


def run_pipeline(topic, limit=20, continue_mode=False):
    # 1. 自动覆写 Scrapy 爬虫的内部配置文件
    settings_path = 'weibo-search/weibo/settings.py'
    with open(settings_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # v1.7.0: 续爬时 Scrapy 的 LIMIT 必须等于已爬取量 + 本次目标新增量
    existing_meta = topic_db.get_topic_meta(topic)

    if continue_mode:
        fetch_limit = existing_meta['total_fetched'] + limit
    else:
        topic_db.clear_topic(topic)
        fetch_limit = limit

    content = re.sub(r"KEYWORD_LIST = \[.*?\]", f"KEYWORD_LIST = ['{topic}']", content)
    content = re.sub(r"LIMIT_RESULT = \d+", f"LIMIT_RESULT = {fetch_limit}", content)
    # 稍微增加延迟或者保持1，用以避开418屏蔽
    content = re.sub(r"DOWNLOAD_DELAY = \d+", "DOWNLOAD_DELAY = 1", content)

    # 动态设置日期范围：最近7天到今天
    from datetime import datetime, timedelta
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    content = re.sub(r"START_DATE = '.*?'", f"START_DATE = '{start_date}'", content)
    content = re.sub(r"END_DATE = '.*?'", f"END_DATE = '{end_date}'", content)

    with open(settings_path, 'w', encoding='utf-8') as f:
        f.write(content)

    csv_path = f'weibo-search/结果文件/{topic}/{topic}.csv'
    # 每次跑之前清理上一次的历史遗留数据
    if os.path.exists(csv_path):
        os.remove(csv_path)

    # 2. 从 Python 子进程内部唤醒终端自动执行 Scrapy
    try:
        subprocess.run(
            ["python", "-m", "scrapy", "crawl", "search"], 
            cwd="weibo-search", 
            check=True, 
            capture_output=True, 
            text=True,
            encoding='gb18030',
            errors='ignore'
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Scrapy 爬虫子进程执行失败(返回码 {e.returncode})\n\n[标准输出]\n{e.stdout}\n\n[错误输出]\n{e.stderr}")

    # 3. 读取刚落地热乎的 CSV，然后顺手并行提取那些账户的主页信息
    if not os.path.exists(csv_path):
        # 爬虫未报错，但未生成文件，说明搜索结果为 0 条
        print(f"[INFO] 话题 '{topic}' 未获取到任何微博数据。")
        return pd.DataFrame(), {'new_fetched': 0, 'total_fetched': existing_meta['total_fetched'], 'has_more': False}

    df = pd.read_csv(csv_path)
    if 'id' in df.columns:
        df = df.drop_duplicates(subset=['id']).copy()

    # --- v1.7.0: 去重 — 与 SQLite 已有记录比对，仅保留新增 ---
    existing_ids = topic_db.get_existing_ids(topic)
    if existing_ids and 'id' in df.columns:
        df['id'] = df['id'].astype(str)
        new_mask = ~df['id'].isin(existing_ids)
        new_count_raw = new_mask.sum()
        df = df[new_mask].copy()
        print(f"[INFO] 去重后新增 {len(df)} 条 (原始 {new_count_raw} 条新, 已有 {len(existing_ids)} 条)")

    if df.empty:
        print(f"[INFO] 话题 '{topic}' 本轮无新增数据，返回历史聚合结果。")
        all_df = topic_db.load_all_posts(topic)
        meta = topic_db.get_topic_meta(topic)
        return all_df, {'new_fetched': 0, 'total_fetched': meta['total_fetched'], 'has_more': True}

    unique_users = df['user_id'].unique()

    # Cookie 统一从 settings.py 读取，不再硬编码
    cookie = _load_cookie_from_settings()
    HEADERS = {
        'cookie': cookie,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36'
    }

    # 使用异步并发获取用户画像（比原同步循环快 5-10 倍）
    user_results = asyncio.run(fetch_all_users_info(unique_users, HEADERS))

    user_features = {r['uid']: r for r in user_results}

    df['followers_count'] = df['user_id'].apply(lambda x: user_features.get(x, {}).get('followers_count', 0))
    df['friends_count'] = df['user_id'].apply(lambda x: user_features.get(x, {}).get('friends_count', 0))
    df['statuses_count'] = df['user_id'].apply(lambda x: user_features.get(x, {}).get('statuses_count', 0))
    df['account_created_at'] = df['user_id'].apply(lambda x: user_features.get(x, {}).get('created_at', ''))
    df['description'] = df['user_id'].apply(lambda x: user_features.get(x, {}).get('description', ''))
    df['avatar_hd'] = df['user_id'].apply(lambda x: user_features.get(x, {}).get('avatar_hd', ''))
    df['recent_post_times'] = df['user_id'].apply(lambda x: user_features.get(x, {}).get('recent_post_times', []))
    df['recent_engagements'] = df['user_id'].apply(lambda x: user_features.get(x, {}).get('recent_engagements', []))
    df['recent_topics'] = df['user_id'].apply(lambda x: user_features.get(x, {}).get('recent_topics', []))
    df['recent_texts'] = df['user_id'].apply(lambda x: user_features.get(x, {}).get('recent_texts', []))
    df['verified_reason'] = df['user_id'].apply(lambda x: user_features.get(x, {}).get('verified_reason', ''))

    for col in ['followers_count', 'friends_count', 'statuses_count']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype('int64')

    # ============================================================
    # 特征工程 (Feature Engineering) — 9 维核心模型特征
    # ============================================================

    # 修复列名映射: weibo_search 爬虫返回的是 '微博正文', 用户昵称为 '用户昵称' 等
    content_col = '微博正文' if '微博正文' in df.columns else '΢'
    df[content_col] = df.get(content_col, df.get('text', pd.Series([''] * len(df)))).astype(str).fillna('')

    name_col = '用户昵称' if '用户昵称' in df.columns else 'ûǳ'
    df[name_col] = df.get(name_col, df.get('ûǳ', pd.Series([''] * len(df)))).astype(str).fillna('')

    # ============================================================
    # 统一特征工程 (Feature Engineering) — 调用 label_existing_data 共享逻辑
    # ============================================================
    from features import compute_model_features

    # 构造用于提取文本特征的长文本 (与 server.py 单账号检测完全对齐：使用近期原创微博组合)
    df['text_for_features'] = df.apply(
        lambda row: ' '.join(row.get('recent_texts', [])[:3]) if isinstance(row.get('recent_texts'), list) and len(row.get('recent_texts', [])) > 0 else str(row.get(content_col, '')),
        axis=1
    )
    
    # 保存原始正文，为了提取特征临时替换
    original_texts = df['微博正文'].copy() if '微博正文' in df.columns else df[content_col].copy()
    df['微博正文'] = df['text_for_features']
    
    # 补充必要字段防止报错
    auth_col = 'user_authentication'
    if auth_col not in df.columns:
        df[auth_col] = df.get('会员类型', pd.Series([''] * len(df))).astype(str).fillna('')
        
    df = compute_model_features(df)

    # v1.9.1 增加单条微博的情感极性，专门用于散点图横坐标展示，避免因为聚合文本导致的情感不准
    from label_existing_data import calc_sentiment
    df['single_sentiment_score'] = original_texts.apply(calc_sentiment)

    # 恢复原始正文用于前端展示，并强制列名为 '微博正文'
    df['微博正文'] = original_texts
    
    if name_col in df.columns and '用户昵称' not in df.columns:
        df['用户昵称'] = df[name_col]

    # 发布工具（保留用于前端展示）
    source_col = '发布工具' if '发布工具' in df.columns else 'source'
    df['source'] = df.get(source_col, df.get('source', pd.Series(['未知'] * len(df))))

    # ============================================================
    # 可疑度评分系统 (v1.8.0 统一评分体系 — 调用 scoring.py)
    # ============================================================
    from scoring import FEATURE_COLS, calc_rule_score, get_model_proba, apply_red_flags, is_official_media

    # --- 步骤 1: 规则评分 ---
    df['rule_suspicion'] = df.apply(calc_rule_score, axis=1)

    # --- 步骤 2: 模型推断 ---
    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = 0

    X = df[FEATURE_COLS].fillna(0)
    model_probs, model_available = get_model_proba(X)
    df['model_confidence'] = model_probs

    # --- 步骤 3: 融合最终可疑度 (80% 模型 + 20% 规则) ---
    if model_available:
        df['suspicion_score'] = (0.2 * df['rule_suspicion'] + 0.8 * df['model_confidence']).round(4)
    else:
        df['suspicion_score'] = df['rule_suspicion']

    # --- 步骤 3.5: 红旗否决机制 ---
    df['suspicion_score'] = df.apply(
        lambda row: apply_red_flags(row['suspicion_score'], row), axis=1
    )

    # --- 新闻媒体及官方豁免 ---
    df['is_official_media'] = df.apply(is_official_media, axis=1).astype(int)
    if model_available:
        news_mask = (df['is_official_media'] == 1)
        df.loc[news_mask, 'suspicion_score'] = df.loc[news_mask, 'suspicion_score'].clip(upper=0.3)

    # 向后兼容
    df['bot_probability'] = df['suspicion_score']
    df['is_bot_pred'] = (df['suspicion_score'] >= 0.7).astype(int)


    # --- v1.7.0: 保存新增数据到 SQLite，然后返回聚合结果 ---
    new_fetched = len(df)
    if 'id' in df.columns:
        df['id'] = df['id'].astype(str)
    topic_db.save_posts(topic, df)

    all_df = topic_db.load_all_posts(topic)
    meta = topic_db.get_topic_meta(topic)

    # 汇总统计
    news_count = int(all_df['is_official_media'].sum()) if 'is_official_media' in all_df.columns else 0

    return all_df, {
        'new_fetched': new_fetched,
        'total_fetched': meta['total_fetched'],
        'news_count': news_count,
        'has_more': True
    }
