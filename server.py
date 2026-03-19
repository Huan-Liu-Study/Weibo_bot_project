from flask import Flask, render_template, request, jsonify
from bot_pipeline import run_pipeline
import traceback
import json
import numpy as np
import pandas as pd
import asyncio
import re

app = Flask(__name__)


# ===================== Helpers =====================

def clean_for_json(df):
    """Convert dataframe to JSON-safe list of dicts, replacing all NaN/NaT with None"""
    import math
    records = df.to_dict('records')
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
            elif isinstance(v, list):
                record[k] = v  # keep lists as-is
            elif pd.isna(v):
                record[k] = None
    return records


def _load_cookie():
    with open('weibo-search/weibo/settings.py', 'r', encoding='utf-8') as f:
        content = f.read()
    match = re.search(r"'cookie'\s*:\s*'([^']+)'", content)
    return match.group(1) if match else ''


# ===================== Routes =====================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/detect', methods=['POST'])
def detect_bots():
    """话题检测 API：输入话题关键词，返回水军检测结果"""
    data = request.json
    topic = data.get('topic', '')
    limit = int(data.get('limit', 15))

    if not topic:
        return jsonify({"error": "请输入有效的微博话题或关键词"}), 400

    try:
        df = run_pipeline(topic, limit)
        return jsonify(build_topic_response(df))
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"流水线执行失败: {str(e)}"}), 500


@app.route('/api/check_user', methods=['POST'])
def check_user():
    """单账号检测 API：输入 UID，返回该用户的可疑度评分和特征"""
    data = request.json
    uid = data.get('uid', '')

    if not uid:
        return jsonify({"error": "请输入有效的微博用户 UID"}), 400

    try:
        result = analyze_single_user(uid)
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"分析失败: {str(e)}"}), 500


# ===================== Business Logic =====================

def build_topic_response(df):
    """Build the standard JSON response for topic detection"""
    total_scanned = len(df)
    bot_count = int(df['is_bot_pred'].sum()) if 'is_bot_pred' in df.columns else 0
    bot_ratio = round(bot_count / total_scanned * 100, 1) if total_scanned > 0 else 0
    overall_sentiment = float(df['sentiment_score'].mean()) if 'sentiment_score' in df.columns else 0.5

    radar_metrics = {}
    if 'is_bot_pred' in df.columns:
        humans_df = df[df['is_bot_pred'] == 0]
        bots_df = df[df['is_bot_pred'] == 1]

        radar_features = [
            'daily_post_rate', 'human_likeness_score',
            'exclamation_density', 'is_random_name', 'engagement_count', 'is_verified',
            'sentiment_score', 'topic_diversity', 'post_interval_variance'
        ]

        radar_metrics['humans'] = {f: float(humans_df[f].mean()) if not humans_df.empty and f in humans_df.columns else 0 for f in radar_features}
        radar_metrics['bots'] = {f: float(bots_df[f].mean()) if not bots_df.empty and f in bots_df.columns else 0 for f in radar_features}

    return {
        "status": "success",
        "summary": {
            "total_scanned": total_scanned,
            "bot_count": bot_count,
            "bot_ratio": bot_ratio,
            "overall_sentiment": overall_sentiment
        },
        "radar_metrics": radar_metrics,
        "suspects": clean_for_json(
            df[df['is_bot_pred'] == 1].sort_values(by='bot_probability', ascending=False).head(10)
        ) if 'is_bot_pred' in df.columns else [],
        "feed": clean_for_json(df.head(20))
    }


def analyze_single_user(uid):
    """分析单个用户的可疑度"""
    import aiohttp
    import joblib
    from label_existing_data import _fetch_one, compute_15_features

    # 1. 获取用户画像
    cookie = _load_cookie()
    headers = {
        'cookie': cookie,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    async def fetch():
        async with aiohttp.ClientSession() as session:
            return await _fetch_one(session, uid, headers)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    user_info = loop.run_until_complete(fetch())
    loop.close()

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
    }])

    df = compute_15_features(df)

    # 3. 模型预测
    feature_cols = [
        'daily_post_rate', 'human_likeness_score',
        'exclamation_density', 'is_random_name', 'engagement_count', 'is_verified',
        'sentiment_score', 'topic_diversity', 'post_interval_variance'
    ]

    for c in feature_cols:
        if c not in df.columns:
            df[c] = 0.0

    X = df[feature_cols].fillna(0)
    features_dict = {c: float(X[c].iloc[0]) for c in feature_cols}

    try:
        model = joblib.load('weibo_bot_rf_model.pkl')
        if hasattr(model, 'predict_proba'):
            probs = model.predict_proba(X)
            score = float(probs[0][1]) if probs.shape[1] > 1 else float(probs[0][0])
        else:
            score = float(model.predict(X)[0])
        score = max(0.0, min(1.0, score))
    except Exception as e:
        print(f"[WARN] Model prediction failed: {e}")
        score = 0.5

    # 4. 生成判定理由
    reasons = generate_reasons(features_dict, score, user_info)

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


def generate_reasons(features, score, user_info):
    """根据特征值生成人类可读的判定理由"""
    reasons = []

    # 发帖间隔方差
    piv = features.get('post_interval_variance', 0)
    if piv < 0.5:
        reasons.append({"level": "high", "text": f"🔴 发帖间隔极其规律（方差={piv:.2f}），疑似定时自动化发帖"})
    elif piv < 1.5:
        reasons.append({"level": "medium", "text": f"🟡 发帖间隔较为规律（方差={piv:.2f}），有一定可疑度"})
    else:
        reasons.append({"level": "low", "text": f"🟢 发帖间隔较随机（方差={piv:.2f}），符合真人行为模式"})

    # 日均发帖率
    dpr = features.get('daily_post_rate', 0)
    if dpr > 3.9:  # log1p(50) ≈ 3.93
        reasons.append({"level": "high", "text": f"🔴 日均发帖率极高（log值={dpr:.2f}），超出正常人类水平"})
    elif dpr > 2.4:  # log1p(10) ≈ 2.40
        reasons.append({"level": "medium", "text": f"🟡 日均发帖率偏高（log值={dpr:.2f}）"})
    else:
        reasons.append({"level": "low", "text": f"🟢 发帖频率正常（log值={dpr:.2f}）"})

    # 互动量
    ec = features.get('engagement_count', 0)
    if ec <= 1.0:
        reasons.append({"level": "high", "text": f"🔴 平均互动量极低（{ec:.1f}），发了帖子无人响应，典型水军特征"})
    elif ec < 5.0:
        reasons.append({"level": "medium", "text": f"🟡 平均互动量偏低（{ec:.1f}）"})
    else:
        reasons.append({"level": "low", "text": f"🟢 互动量健康（{ec:.1f}），有正常的社交互动"})

    # 语义拟人度
    hl = features.get('human_likeness_score', 0)
    if hl < 0.2:
        reasons.append({"level": "high", "text": f"🔴 文本语义拟人度极低（{hl:.2f}），内容像模板生成"})
    elif hl > 0.5:
        reasons.append({"level": "low", "text": f"🟢 文本内容自然丰富（拟人度={hl:.2f}），像真人撰写"})

    # 话题多样性
    td = features.get('topic_diversity', 0)
    if td < 0.2:
        reasons.append({"level": "high", "text": f"🔴 话题多样性极低（{td:.2f}），疑似长期刷单一话题"})
    elif td > 0.7:
        reasons.append({"level": "low", "text": f"🟢 话题涉猎广泛（多样性={td:.2f}）"})

    # 乱码昵称
    if features.get('is_random_name', 0) == 1:
        reasons.append({"level": "high", "text": "🔴 用户昵称含5位以上连续数字，疑似批量注册账号"})

    # V认证
    vr = user_info.get('verified_reason', '')
    if vr:
        reasons.append({"level": "low", "text": f"🟢 已通过微博认证：{vr}"})

    return reasons


# ===================== Entry =====================

if __name__ == '__main__':
    app.run(debug=True, port=5000, use_reloader=False)
