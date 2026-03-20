from flask import Flask, render_template, request, jsonify
from bot_pipeline import run_pipeline
import traceback
import json
import numpy as np
import pandas as pd
import asyncio
import re
import topic_db
from collections import Counter
from snownlp import SnowNLP


app = Flask(__name__)


# ===================== Helpers =====================

def clean_for_json(df):
    """Convert dataframe or list to JSON-safe list of dicts, replacing all NaN/NaT with None"""
    import math
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


# ===================== WordCloud Logic (v1.9.40) =====================

STOPWORDS = set([
    '的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你',
    '会', '着', '没', '看', '好', '自己', '这', '让', '那', '点', '还', '个', '把', '多', '去', '被', '走', '对', '谁', '太', '再',
    '里', '后', '想', '打', '起来', '过', '得', '能', '下', '等', '把', '我们', '你们', '他们', '它们', '微博', '分享', '链接', '全文',
    '转发', '哈哈', '表情', '视频', '图片', '今天', '一个', '就是', '还是', '怎么', '感觉', '真的', '现在', '因为', '所以', '如果', '但是',
    '开始', '发现', '已经', '看到', '出来', '还有', '一下', '非常', '比较', '这种', '那个', '这里', '那里', '其实', '可能', '所以', '知道'
])

def generate_wordcloud_data(texts, top_n=50):
    """使用 SnowNLP 进行分词并统计词频"""
    words = []
    for text in texts:
        if not text or not isinstance(text, str):
            continue
        try:
            # 过滤掉非中文字符，保留关键词质量
            clean_text = re.sub(r'[^\u4e00-\u9fa5]', '', text)
            if len(clean_text) < 2:
                continue
            s = SnowNLP(clean_text)
            for w in s.words:
                if len(w) > 1 and w not in STOPWORDS:
                    words.append(w)
        except:
            continue
            
    counts = Counter(words).most_common(top_n)
    return [{"name": k, "value": v} for k, v in counts]




def _load_cookie():
    with open('weibo-search/weibo/settings.py', 'r', encoding='utf-8') as f:
        content = f.read()
    match = re.search(r"'cookie'\s*:\s*'([^']+)'", content)
    return match.group(1) if match else ''


# ===================== Routes =====================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/history', methods=['GET'])
def get_history():
    """获取所有历史话题的列表"""
    try:
        topics = topic_db.get_all_topics()
        return jsonify({"status": "success", "topics": topics})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/delete_topic', methods=['POST'])
def delete_topic():
    """删除特定话题的数据"""
    data = request.json
    topic = data.get('topic', '')
    if not topic:
        return jsonify({"error": "缺少话题参数"}), 400
    try:
        topic_db.clear_topic(topic)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/detect', methods=['POST'])
def detect_bots():
    """话题检测 API：输入话题关键词，返回水军检测结果（支持断点续爬及历史加载）"""
    data = request.json
    topic = data.get('topic', '')
    limit = int(data.get('limit', 15))
    continue_mode = bool(data.get('continue', False))
    action = data.get('action', 'fetch')  # 'fetch' or 'load'

    if not topic:
        return jsonify({"error": "请输入有效的微博话题或关键词"}), 400

    try:
        if action == 'load':
            df = topic_db.load_all_posts(topic)
            if df.empty:
                return jsonify({"error": f"未找到话题 '{topic}' 的历史数据"}), 404
            meta = topic_db.get_topic_meta(topic)
            crawl_info = {'new_fetched': 0, 'total_fetched': meta['total_fetched'], 'has_more': True}
        else:
            df, crawl_info = run_pipeline(topic, limit, continue_mode=continue_mode)
            
        if df.empty and action != 'load':
            return jsonify({"error": "未获取到任何数据，可能是被反爬或数据为空。"})

        response = build_topic_response(df)
        response['crawl_info'] = crawl_info
        return jsonify(response)
    except Exception as e:
        tb = traceback.format_exc()
        return jsonify({"error": f"执行失败: {str(e)}\n\nTRACEBACK:\n{tb}"}), 500



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
    if total_scanned == 0:
        overall_sentiment = 0.5
    else:
        mean_val = df['sentiment_score'].mean() if 'sentiment_score' in df.columns else 0.5
        overall_sentiment = float(mean_val) if pd.notna(mean_val) else 0.5

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

    all_nodes_list = []
    if 'is_bot_pred' in df.columns:
        feature_cols = [
            'daily_post_rate', 'human_likeness_score',
            'exclamation_density', 'is_random_name', 'engagement_count', 'is_verified',
            'sentiment_score', 'topic_diversity', 'post_interval_variance'
        ]
        # v1.9.0 构造全量节点数据，用于支持散点图可视化与点击弹窗
        for _, row in df.iterrows():
            node_dict = {
                'user_id': str(row.get('user_id', '')),
                'name': str(row.get('用户昵称', '')),
                'text': str(row.get('微博正文', '')),
                'sentiment_score': float(row.get('sentiment_score', 0.5)),
                'single_sentiment_score': float(row.get('single_sentiment_score', row.get('sentiment_score', 0.5))),
                'suspicion_score': float(row.get('bot_probability', 0)),
                'is_bot_pred': int(row.get('is_bot_pred', 0)),
                'is_news_media': int(row.get('is_news_media', 0)),
                'followers_count': int(row.get('followers_count', 0)),
                'statuses_count': int(row.get('statuses_count', 0))
            }
            features_dict = {c: float(row.get(c, 0)) for c in feature_cols}
            node_dict['features'] = features_dict
            
            score = float(row.get('bot_probability', 0))
            user_info = {
                'verified_reason': str(row.get('verified_reason', '')),
                'description': str(row.get('description', ''))
            }
            node_dict['reasons'] = generate_reasons(features_dict, score, user_info)
            node_dict['has_red_flag'] = any(r.get('is_red_flag') for r in node_dict['reasons'])
            all_nodes_list.append(node_dict)


    suspects_list = []
    if 'is_bot_pred' in df.columns:
        suspects_df = df[df['is_bot_pred'] == 1].sort_values(by='bot_probability', ascending=False)

        feature_cols = [
            'daily_post_rate', 'human_likeness_score',
            'exclamation_density', 'is_random_name', 'engagement_count', 'is_verified',
            'sentiment_score', 'topic_diversity', 'post_interval_variance'
        ]
        for _, row in suspects_df.iterrows():
            suspect_dict = row.to_dict()
            features_dict = {c: float(row.get(c, 0)) for c in feature_cols}
            score = float(row.get('bot_probability', 0))
            user_info = {
                'verified_reason': str(row.get('verified_reason', '')),
                'description': str(row.get('description', ''))
            }
            suspect_dict['reasons'] = generate_reasons(features_dict, score, user_info)
            suspects_list.append(suspect_dict)

    return {
        "status": "success",
        "summary": {
            "total_scanned": total_scanned,
            "bot_count": bot_count,
            "news_count": int(df['is_news_media'].sum()) if 'is_news_media' in df.columns else 0,
            "bot_ratio": bot_ratio,
            "overall_sentiment": overall_sentiment
        },
        "radar_metrics": radar_metrics,
        "suspects": clean_for_json(suspects_list),
        "all_nodes": clean_for_json(all_nodes_list),
        "wordclouds": {
            "humans": generate_wordcloud_data(df[(df['is_bot_pred'] == 0) & (df['is_news_media'] == 0)]['微博正文'].tolist()),
            "bots": generate_wordcloud_data(df[df['is_bot_pred'] == 1]['微博正文'].tolist())
        },
        "feed": clean_for_json(df.head(20))
    }


def analyze_single_user(uid):
    """分析单个用户的可疑度"""
    import aiohttp
    import joblib
    from label_existing_data import _fetch_one, compute_model_features

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

    df = compute_model_features(df)

    # 3. 统一评分 (v1.8.0 — 与话题检测使用同一套评分体系)
    from scoring import FEATURE_COLS, compute_final_score, get_model_proba

    for c in FEATURE_COLS:
        if c not in df.columns:
            df[c] = 0.0

    X = df[FEATURE_COLS].fillna(0)
    features_dict = {c: float(X[c].iloc[0]) for c in FEATURE_COLS}

    model_probs, _ = get_model_proba(X)
    model_prob = float(model_probs[0])

    # 构造 row dict 供 compute_final_score 使用 (需含 verified_reason)
    row_dict = {**features_dict, 'verified_reason': user_info.get('verified_reason', '')}
    score = compute_final_score(features_dict, model_prob, row_dict)

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
    from scoring import is_news_media
    reasons = []

    # 优先检查新闻媒体豁免 (v1.9.15)
    # 构造合规的 row 字典供 is_news_media 使用
    row_check = {
        'verified_reason': user_info.get('verified_reason', ''),
        'description': user_info.get('description', ''),
        'screen_name': user_info.get('screen_name', ''),
        '用户昵称': user_info.get('screen_name', ''),
        'is_verified': 1 if user_info.get('verified_reason') else 0
    }
    if is_news_media(row_check):
        reasons.append({
            "level": "low", 
            "text": "✅ 系统识其为媒体/官方机构：已执行豁免算法，大幅降低评分权重，降低误报。"
        })


    # 发帖间隔方差
    piv = features.get('post_interval_variance', 0)
    if piv < 0.69:  # log1p(1) ≈ 0.693, see scoring.py 红旗1
        reasons.append({"level": "high", "is_red_flag": True, "text": f"🚩 红旗预警：发帖间隔极其机械化（方差={piv:.2f}），已触发系统自动拦截机制"})
    elif piv < 1.5:
        reasons.append({"level": "medium", "text": f"🟡 发帖间隔较为规律（方差={piv:.2f}），有一定可疑度"})
    else:
        reasons.append({"level": "low", "text": f"低危：发帖间隔较随机（方差={piv:.2f}）"})

    # 日均发帖率
    dpr = features.get('daily_post_rate', 0)
    if dpr >= 3.93:  # log1p(50) = 3.93, see scoring.py 红旗2
        reasons.append({"level": "high", "is_red_flag": True, "text": f"🚩 红旗预警：日均发帖量极高（log值={dpr:.2f}），超出人类极限，判定为机器代发"})
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
    if td <= 0.1:  # scoring.py 红旗3
        reasons.append({"level": "high", "is_red_flag": True, "text": f"🚩 红旗预警：话题分布极其狭隘（多样性={td:.2f}），明显属于工业化刷榜脚本"})
    elif td < 0.2:
        reasons.append({"level": "high", "text": f"🔴 话题多样性极低（{td:.2f}），疑似长期刷单一话题"})
    elif td > 0.7:
        reasons.append({"level": "low", "text": f"低危：话题涉猎广泛（多样性={td:.2f}）"})

    # 乱码昵称
    if features.get('is_random_name', 0) == 1:
        reasons.append({"level": "high", "text": "🔴 乱码昵称：识别为系统随机生成的数字乱码，符合批量注册特征"})



    # 感叹号密度
    ed = features.get('exclamation_density', 0)
    if ed > 0.1:
        reasons.append({"level": "medium", "text": f"🟡 文本感叹号密度极高（{ed*100:.1f}%），带有强烈情绪诱导特征"})

    # 情感得分
    ss = features.get('sentiment_score', 0.5)
    if ss < 0.2:
        reasons.append({"level": "medium", "text": f"🟡 情感倾向极负面（{ss:.2f}），可能涉及负面舆论引导"})
    elif ss > 0.8:
        reasons.append({"level": "low", "text": f"🟢 情感倾向积极正面（{ss:.2f}）"})

    # V认证
    vr = user_info.get('verified_reason', '')
    if vr:
        reasons.append({"level": "low", "text": f"🟢 已通过微博认证：{vr}"})

    return reasons


# ===================== Entry =====================

if __name__ == '__main__':
    app.run(debug=True, port=5000, use_reloader=False)
