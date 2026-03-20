import math
import numpy as np
import pandas as pd
import asyncio
import aiohttp

from wordcloud_utils import generate_wordcloud_data
from reasons import generate_reasons
from scoring import FEATURE_COLS, compute_final_score, get_model_proba
from config import load_cookie
from features import compute_model_features
from weibo_api import fetch_user_profile_and_timeline

def clean_for_json(df):
    """Convert dataframe or list to JSON-safe list of dicts, replacing all NaN/NaT with None"""
    if hasattr(df, 'to_dict'):
        records = df.to_dict('records')
    else:
        records = df
    for record in records:
        for k, v in list(record.items()):
            if v is None:
                continue
            elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                record[k] = None
            elif isinstance(v, (np.int64, np.int32)):
                record[k] = int(v)
            elif isinstance(v, (np.float64, np.float32)):
                if np.isnan(v) or np.isinf(v):
                    record[k] = None
                else:
                    record[k] = float(v)
            elif isinstance(v, np.bool_):
                record[k] = bool(v)
            elif hasattr(v, 'isoformat'):
                record[k] = str(v)
            elif isinstance(v, (list, dict)):
                record[k] = v  # keep lists/dicts as-is, skip pd.isna check
            elif isinstance(v, str):
                continue  # strings are fine as-is
            else:
                try:
                    if pd.isna(v):
                        record[k] = None
                except (ValueError, TypeError):
                    pass  # if pd.isna fails, keep original value
    return records


def build_topic_response(df):
    """Build the standard JSON response for topic detection"""
    total_scanned = len(df)
    bot_count = int(df['is_bot_pred'].sum()) if 'is_bot_pred' in df.columns else 0
    bot_ratio = round(bot_count / total_scanned * 100, 1) if total_scanned > 0 else 0
    if total_scanned == 0:
        overall_sentiment = 0.5
    else:
        mean_val = df['sentiment_score'].mean() if 'sentiment_score' in df.columns else 0.5
        overall_sentiment = float(mean_val) if pd.notna(mean_val) else 0.5

    radar_metrics = {}
    if 'is_bot_pred' in df.columns:
        humans_df = df[df['is_bot_pred'] == 0]
        bots_df = df[df['is_bot_pred'] == 1]

        radar_metrics['humans'] = {f: float(humans_df[f].mean()) if not humans_df.empty and f in humans_df.columns else 0 for f in FEATURE_COLS}
        radar_metrics['bots'] = {f: float(bots_df[f].mean()) if not bots_df.empty and f in bots_df.columns else 0 for f in FEATURE_COLS}

    all_nodes_list = []
    if 'is_bot_pred' in df.columns:
        for _, row in df.iterrows():
            node_dict = {
                'user_id': str(row.get('user_id', '')),
                'name': str(row.get('用户昵称', '')),
                'text': str(row.get('微博正文', '')),
                'sentiment_score': float(row.get('sentiment_score', 0.5)),
                'single_sentiment_score': float(row.get('single_sentiment_score', row.get('sentiment_score', 0.5))),
                'is_official_media': int(row.get('is_official_media', 0)),
                'suspicion_score': float(row.get('bot_probability', 0)),
                'is_bot_pred': int(row.get('is_bot_pred', 0)),
                'followers_count': int(row.get('followers_count', 0)),
                'statuses_count': int(row.get('statuses_count', 0))
            }
            features_dict = {c: float(row.get(c, 0)) for c in FEATURE_COLS}
            node_dict['features'] = features_dict
            
            score = float(row.get('bot_probability', 0))
            user_info = {
                'verified_reason': str(row.get('verified_reason', '')),
                'description': str(row.get('description', '')),
                'screen_name': str(row.get('用户昵称', '')),
                'user_authentication': str(row.get('user_authentication', ''))
            }
            node_dict['reasons'] = generate_reasons(features_dict, score, user_info)
            node_dict['has_red_flag'] = any(r.get('is_red_flag') for r in node_dict['reasons'])
            all_nodes_list.append(node_dict)

    suspects_list = []
    if 'is_bot_pred' in df.columns:
        suspects_df = df[df['is_bot_pred'] == 1].sort_values(by='bot_probability', ascending=False)
        for _, row in suspects_df.iterrows():
            suspect_dict = row.to_dict()
            features_dict = {c: float(row.get(c, 0)) for c in FEATURE_COLS}
            score = float(row.get('bot_probability', 0))
            user_info = {
                'verified_reason': str(row.get('verified_reason', '')),
                'description': str(row.get('description', '')),
                'screen_name': str(row.get('用户昵称', '')),
                'user_authentication': str(row.get('user_authentication', ''))
            }
            suspect_dict['reasons'] = generate_reasons(features_dict, score, user_info)
            suspects_list.append(suspect_dict)

    avg_score = df['bot_probability'].mean() if 'bot_probability' in df.columns and not df.empty else 0.0

    return {
        "status": "success",
        "summary": {
            "total_scanned": total_scanned,
            "bot_count": bot_count,
            "news_count": int(df['is_official_media'].sum()) if 'is_official_media' in df.columns else 0,
            "overall_bot_ratio": bot_ratio,
            "avg_bot_score": avg_score,
            "overall_sentiment": overall_sentiment
        },
        "radar_metrics": radar_metrics,
        "suspects": clean_for_json(suspects_list),
        "all_nodes": clean_for_json(all_nodes_list),
        "wordclouds": {
            "humans": generate_wordcloud_data(df[(df['is_bot_pred'] == 0) & (df['is_official_media'] == 0)]['微博正文'].tolist()),
            "bots": generate_wordcloud_data(df[df['is_bot_pred'] == 1]['微博正文'].tolist())
        },
        "feed": clean_for_json(df.head(20))
    }


def analyze_single_user(uid):
    """分析单个用户的可疑度"""
    cookie = load_cookie()
    headers = {
        'cookie': cookie,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    async def fetch():
        async with aiohttp.ClientSession() as session:
            return await fetch_user_profile_and_timeline(session, uid, headers)

    try:
        user_info = asyncio.run(fetch())
    except Exception as e:
        print(f"Error fetching user: {e}")
        user_info = None

    if not user_info or user_info.get('followers_count', 0) == 0 and not user_info.get('screen_name'):
        return {"error": f"无法获取 UID={uid} 的用户信息，请检查 UID 是否正确或 Cookie 是否过期"}

    # 2. 构建 DataFrame 并计算特征
    df = pd.DataFrame([{
        'user_id': uid,
        '用户昵称': user_info.get('screen_name', ''),
        '微博正文': ' '.join(user_info.get('recent_texts', [])[:3]) if user_info.get('recent_texts') else '',
        'followers_count': user_info.get('followers_count', 0),
        'friends_count': user_info.get('friends_count', 0),
        'statuses_count': user_info.get('statuses_count', 0),
        'description': user_info.get('description', ''),
        'avatar_hd': user_info.get('avatar_hd', ''),
        'recent_post_times': user_info.get('recent_post_times', []),
        'recent_engagements': user_info.get('recent_engagements', []),
        'recent_topics': user_info.get('recent_topics', []),
        'verified_reason': user_info.get('verified_reason', ''),
        'user_authentication': user_info.get('user_authentication', '')
    }])

    df = compute_model_features(df)

    # 3. 统一评分
    for c in FEATURE_COLS:
        if c not in df.columns:
            df[c] = 0.0

    X = df[FEATURE_COLS].fillna(0)
    features_dict = {c: float(X[c].iloc[0]) for c in FEATURE_COLS}

    model_probs, _ = get_model_proba(X)
    model_prob = float(model_probs[0])

    row_dict = {
        **features_dict, 
        'verified_reason': user_info.get('verified_reason', ''),
        'description': user_info.get('description', ''),
        'screen_name': user_info.get('screen_name', ''),
        'user_authentication': user_info.get('user_authentication', '')
    }
    score = compute_final_score(features_dict, model_prob, row_dict)

    # 4. 生成判定理由
    reasons = generate_reasons(features_dict, score, dict(row_dict))

    # 5. 映射标签
    if score < 0.125: label = 0
    elif score < 0.375: label = 1
    elif score < 0.625: label = 2
    elif score < 0.875: label = 3
    else: label = 4

    return {
        "status": "success",
        "user_info": {
            "uid": uid,
            "screen_name": user_info.get('screen_name', ''),
            "followers_count": user_info.get('followers_count', 0),
            "friends_count": user_info.get('friends_count', 0),
            "statuses_count": user_info.get('statuses_count', 0),
            "avatar_hd": user_info.get('avatar_hd', ''),
            "description": str(user_info.get('description', ''))[:100],
            "verified_reason": user_info.get('verified_reason', ''),
        },
        "suspicion_score": round(score, 4),
        "suspicion_label": label,
        "features": features_dict,
        "reasons": reasons
    }
