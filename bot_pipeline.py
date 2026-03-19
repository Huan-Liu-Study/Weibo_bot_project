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
    settings_path = 'weibo-search/weibo/settings.py'
    with open(settings_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # 提取 'cookie': '...' 中的值
    match = re.search(r"'cookie'\s*:\s*'([^']+)'", content)
    if match:
        return match.group(1)
    return ''


async def fetch_user_info(session, uid, headers):
    """异步获取单个用户的画像数据（扩展字段版）"""
    info_url = f'https://weibo.com/ajax/profile/info?custom={uid}'
    current_headers = headers.copy()
    current_headers['Referer'] = f'https://weibo.com/u/{uid}'
    current_headers['Accept'] = 'application/json, text/plain, */*'

    result = {
        'uid': uid,
        'followers_count': 0,
        'statuses_count': 0,
        'created_at': '',
        'description': '',
        'avatar_hd': '',
        'recent_post_times': [],
        'recent_engagements': [],
        'recent_topics': [],
        'verified_reason': '',
    }

    try:
        # 增加一点随机延迟，防止并发过高被拒绝服务
        await asyncio.sleep(0.1)
        async with session.get(info_url, headers=current_headers, timeout=5) as response:
            if response.status == 200:
                data = await response.json()
                user_info = data.get('data', {}).get('user', {})
                if user_info:
                    result['followers_count'] = user_info.get('followers_count', 0)
                    result['statuses_count'] = user_info.get('statuses_count', 0)
                    result['created_at'] = user_info.get('created_at', '')
                    result['description'] = user_info.get('description', '')
                    result['avatar_hd'] = user_info.get('avatar_hd', '')
                    result['verified_reason'] = user_info.get('verified_reason', '')
    except Exception as e:
        print(f"Fetch info failed for {uid}: {e}")

    # 获取近期发帖列表 (用于时序特征)
    timeline_url = f'https://weibo.com/ajax/statuses/mymblog?uid={uid}&page=1&feature=0'
    try:
        await asyncio.sleep(0.1)
        async with session.get(timeline_url, headers=current_headers, timeout=5) as response:
            if response.status == 200:
                data = await response.json()
                posts = data.get('data', {}).get('list', [])
                if posts:
                    result['recent_post_times'] = [p.get('created_at') for p in posts if p.get('created_at')]
                    
                    # ⚠️ 关键修正2：必须是该用户自己发的原创帖，不能是转发，也不能是点赞别人的帖子
                    # 别人发的帖子会出现在 timeline 是因为“赞过的微博”等机制，绝对不能算作自己的互动！
                    eng_list = []
                    topics_list = []
                    uid_str = str(uid)
                    for p in posts:
                        is_own_post = str(p.get('user', {}).get('id', '')) == uid_str
                        is_retweet = 'retweeted_status' in p
                        text = p.get('text_raw', p.get('text', ''))
                        
                        is_valid_post = False
                        if is_own_post:
                            if not is_retweet:
                                is_valid_post = True
                            else:
                                # 检查是否为带有 5 个字以上自定义评论的转发
                                import re
                                custom_comment = text.split('//')[0]
                                custom_comment = re.sub(r'转发微博|Repost|回复@\S+:', '', custom_comment).strip()
                                if len(custom_comment) > 5:
                                    is_valid_post = True
                                    
                        if is_valid_post:
                            eng = p.get('reposts_count', 0) + p.get('comments_count', 0) + p.get('attitudes_count', 0)
                            eng_list.append(eng)
                            
                            # 提取特征：话题多样性
                            import re
                            found_topics = re.findall(r'#([^#]+)#', text)
                            if found_topics:
                                topics_list.extend(found_topics)
                    
                    result['recent_engagements'] = eng_list
                    result['recent_topics'] = topics_list
    except Exception as e:
        print(f"Fetch timeline failed for {uid}: {e}")

    return result


async def fetch_all_users_info(uids, headers):
    """并发获取所有用户画像"""
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_user_info(session, uid, headers) for uid in uids]
        return await asyncio.gather(*tasks)


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
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    user_results = loop.run_until_complete(fetch_all_users_info(unique_users, HEADERS))
    loop.close()

    user_features = {r['uid']: r for r in user_results}

    df['followers_count'] = df['user_id'].apply(lambda x: user_features.get(x, {}).get('followers_count', 0))
    df['statuses_count'] = df['user_id'].apply(lambda x: user_features.get(x, {}).get('statuses_count', 0))
    df['account_created_at'] = df['user_id'].apply(lambda x: user_features.get(x, {}).get('created_at', ''))
    df['description'] = df['user_id'].apply(lambda x: user_features.get(x, {}).get('description', ''))
    df['avatar_hd'] = df['user_id'].apply(lambda x: user_features.get(x, {}).get('avatar_hd', ''))
    df['recent_post_times'] = df['user_id'].apply(lambda x: user_features.get(x, {}).get('recent_post_times', []))
    df['recent_engagements'] = df['user_id'].apply(lambda x: user_features.get(x, {}).get('recent_engagements', []))
    df['recent_topics'] = df['user_id'].apply(lambda x: user_features.get(x, {}).get('recent_topics', []))
    df['verified_reason'] = df['user_id'].apply(lambda x: user_features.get(x, {}).get('verified_reason', ''))

    for col in ['followers_count', 'statuses_count']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype('int64')

    # ============================================================
    # 特征工程 (Feature Engineering) — 9 维核心模型特征
    # ============================================================

    # 修复列名映射: weibo_search 爬虫返回的是 '微博正文', 用户昵称为 '用户昵称' 等
    content_col = '微博正文' if '微博正文' in df.columns else '΢'
    df[content_col] = df.get(content_col, df.get('text', pd.Series([''] * len(df)))).astype(str).fillna('')

    name_col = '用户昵称' if '用户昵称' in df.columns else 'ûǳ'
    df[name_col] = df.get(name_col, df.get('ûǳ', pd.Series([''] * len(df)))).astype(str).fillna('')

    # --- 特征 1: daily_post_rate （近期实际日均发帖率）---
    # 使用 API 返回的近 ~20 条帖子的时间戳计算真实的近期发帖频率
    # 公式: 帖子数 / 时间跨度天数
    def get_daily_rate(row):
        times_list = row.get('recent_post_times', [])
        if not times_list or not isinstance(times_list, list) or len(times_list) < 2:
            return 0.0
        try:
            dts = sorted([pd.to_datetime(t).replace(tzinfo=None) for t in times_list])
            span_days = (dts[-1] - dts[0]).total_seconds() / 86400.0  # 最新帖到最老帖的天数
            if span_days < 0.01:
                rate = float(len(times_list))
            else:
                rate = len(times_list) / span_days
            return float(min(50.0, rate))

        except Exception:
            return 0.0

    df['daily_post_rate'] = df.apply(get_daily_rate, axis=1)

    # --- 特征 3: human_likeness_score (替换 text_len) ---
    def _calc_human_likeness(text):
        if not isinstance(text, str) or not text.strip(): return 0.0
        
        # 清理话题标签等无关内容
        clean_text = re.sub(r'#.*?#', '', text)
        clean_text = re.sub(r'@[\u4e00-\u9fa5a-zA-Z0-9_-]+', '', clean_text)
        clean_text = re.sub(r'https?://[^\s]+', '', clean_text)
        clean_text = re.sub(r'\[.*?\]', '', clean_text) # 过滤表情
        clean_text = re.sub(r'[^\u4e00-\u9fa5]', '', clean_text) # 仅保留中文字符用于计算
        
        if len(clean_text) < 3: return 0.0
        
        # 1. 词汇丰富度 (40%)：去重字符占总字符比
        diversity = len(set(clean_text)) / len(clean_text)
        
        # 2. 主观情绪词密度 (30%)
        subjective_words = ['我', '觉得', '认为', '太', '怎么', '感觉', '真的', '其实', '居然', '没想到']
        subj_count = sum(1 for w in subjective_words if w in text)
        subjectivity = min(1.0, subj_count / 3.0) # 3个主观词即满分
        
        # 3. 复句复杂度 (30%)
        complex_words = ['虽然', '但是', '如果', '就', '哪怕', '因为', '所以', '不仅', '而且', '与其', '不如']
        comp_count = sum(1 for w in complex_words if w in text)
        complexity = min(1.0, comp_count / 2.0) # 2个连词即满分
        
        return float((diversity * 0.4) + (subjectivity * 0.3) + (complexity * 0.3))

    df['human_likeness_score'] = df[content_col].apply(_calc_human_likeness)

    # --- 特征 3: exclamation_density （感叹号密度）---
    def calc_exclamation_density(text):
        if len(text) == 0:
            return 0.0
        return (text.count('!') + text.count('！')) / len(text)

    df['exclamation_density'] = df[content_col].apply(calc_exclamation_density)

    # --- 特征 7: is_random_name （是否数字乱码昵称）---
    df['is_random_name'] = df[name_col].apply(lambda x: 1 if re.search(r'\d{5,}', x) else 0)

    # --- 特征 8: engagement_count （互动率 = 近20条转+评+赞平均值，原 zero_engagement）---
    def calc_recent_engagement(eng_list):
        if not eng_list or not isinstance(eng_list, list): return 1.0 # 护盾
        try: eng_list = [float(x) for x in eng_list]
        except Exception: return 1.0 # 护盾
        if len(eng_list) == 0: return 1.0 # 护盾
        
        avg_eng = sum(eng_list) / len(eng_list)
        return max(1.0, avg_eng) # 兜底保护低调素人

    df['engagement_count'] = df.apply(lambda r: calc_recent_engagement(r.get('recent_engagements', [])), axis=1)

    # --- 特征 9: is_verified （是否V认证）---
    auth_col = 'user_authentication'
    df[auth_col] = df.get(auth_col, df.get('会员类型', pd.Series([''] * len(df)))).astype(str).fillna('')
    df['is_verified'] = df[auth_col].apply(lambda x: 1 if 'V' in x or '认证' in x else 0)

    # --- 特征 10: sentiment_score （情感极性，之前遗漏未入模型）---
    def _get_sentiment(text):
        from snownlp import SnowNLP
        clean = re.sub(r"http\S+", "", str(text)).strip()
        if not clean: return 0.5
        # 截取前100字符，防止朴素贝叶斯连乘极化
        clean = clean[:100]
        try: return round(SnowNLP(clean).sentiments, 4)
        except: return 0.5

    df['sentiment_score'] = df[content_col].apply(_get_sentiment)

    # --- 特征 10: sentiment_score （情感极性）---

    # --- 特征 13: topic_diversity (取代旧的urank) ---
    # 计算公式: 独立话题数量 / 近期发帖总数 (没发帖或没话题则为0)
    def calc_topic_diversity(row):
        topics = row.get('recent_topics', [])
        times_list = row.get('recent_post_times', [])
        if not isinstance(times_list, list) or len(times_list) == 0:
            return 0.5
        n_posts = len(times_list)
        if not isinstance(topics, list):
            topics = []
        m_tags = len(topics)
        unique_tags = len(set(topics))
        untagged_posts = max(0, n_posts - m_tags)
        score = (unique_tags + untagged_posts) / n_posts
        return float(min(1.0, score))

        
    df['topic_diversity'] = df.apply(calc_topic_diversity, axis=1)

    # --- 特征 13: topic_diversity ---

    # --- 特征 15: post_interval_variance （近期发帖时间间隔方差，时序核心特征）---
    def _calc_variance(times_list):
        if not times_list or len(times_list) < 2:
            return 0.0
        try:
            dts = [pd.to_datetime(t).replace(tzinfo=None) for t in times_list]
            dts.sort()
            intervals = [(dts[i+1] - dts[i]).total_seconds() / 3600.0 for i in range(len(dts)-1)]
            return float(np.std(intervals))
        except:
            return 0.0

    df['post_interval_variance'] = df.get('recent_post_times', pd.Series([[]]*len(df))).apply(_calc_variance)

    # ====== log1p scaling (aligned with label_existing_data.py) ======
    for col in ['daily_post_rate', 'post_interval_variance']:
        if col in df.columns:
            df[col] = np.log1p(df[col].clip(lower=0))


    # 发布工具（保留用于前端展示）
    source_col = '发布工具' if '发布工具' in df.columns else 'source'
    df['source'] = df.get(source_col, df.get('source', pd.Series(['未知'] * len(df))))

    # 强制统一列名以返回前端展示
    if '微博正文' not in df.columns and content_col in df.columns:
        df['微博正文'] = df[content_col]

    if '用户昵称' not in df.columns and name_col in df.columns:
        df['用户昵称'] = df[name_col]

    # ============================================================
    # 可疑度评分系统 (v1.8.0 统一评分体系 — 调用 scoring.py)
    # ============================================================
    from scoring import FEATURE_COLS, calc_rule_score, get_model_proba, apply_red_flags, is_news_media

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

    # --- 新闻媒体豁免 ---
    if model_available:
        news_mask = df.apply(is_news_media, axis=1)
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

    return all_df, {
        'new_fetched': new_fetched,
        'total_fetched': meta['total_fetched'],
        'has_more': True
    }
