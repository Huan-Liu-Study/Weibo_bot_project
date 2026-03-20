import ast
import pandas as pd
import numpy as np
import re
from snownlp import SnowNLP

def calc_sentiment(text):
    """
    v1.9.1 增强型情感分析计算
    """
    if not text or not isinstance(text, str): return 0.5
    # 1. 基础清理
    clean = re.sub(r"http\S+", "", text)
    # 2. 增强清理：针对 [打call] 等微博特色表情符号及话题标签
    clean = re.sub(r"\[.*?\]", "", clean)
    clean = re.sub(r"#.*?#", "", clean)
    clean = clean.strip()
    
    if not clean: return 0.5
    
    # 3. 截断防止模型极化
    sample = clean[:100]
    try:
        score = SnowNLP(sample).sentiments
        return round(score, 4)
    except Exception:
        return 0.5

def compute_model_features(df):
    cc = '微博正文' if '微博正文' in df.columns else 'text'

    nc = '用户昵称' if '用户昵称' in df.columns else 'screen_name'
    df[cc] = df[cc].astype(str).fillna('')
    df[nc] = df[nc].astype(str).fillna('')

    for c in ['followers_count', 'friends_count', 'statuses_count']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)

    # ====== 统一解析：将 CSV 中存储的字符串格式列表还原为 Python list ======
    def _parse_list(val):
        if isinstance(val, list):
            return val
        if isinstance(val, str) and val.startswith('['):
            try:
                return ast.literal_eval(val)
            except Exception:
                return []
        return []

    for list_col in ['recent_post_times', 'recent_engagements', 'recent_topics']:
        if list_col in df.columns:
            df[list_col] = df[list_col].apply(_parse_list)


    # 使用 API 返回的近 ~20 条帖子的时间戳计算真实的近期发帖频率
    def _dpr(row):
        times_list = row.get('recent_post_times', [])
        if not times_list or not isinstance(times_list, list) or len(times_list) < 2:
            return 0.0
        try:
            dts = sorted([pd.to_datetime(t).replace(tzinfo=None) for t in times_list])
            span_days = (dts[-1] - dts[0]).total_seconds() / 86400.0
            if span_days < 0.01:  # 所有帖子几乎同时发
                rate = float(len(times_list))
            else:
                rate = len(times_list) / span_days
            # 强制盖帽：每天最多算 50 贴（超过这个量对判别水军已经没有意义，只会制造特征极化的噪音）
            return float(min(50.0, rate))
        except Exception: return 0.0
    df['daily_post_rate'] = df.apply(_dpr, axis=1)

    # 3 human_likeness_score (替换 text_len)
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

    df['human_likeness_score'] = df[cc].apply(_calc_human_likeness)

    # 4 exclamation_density
    df['exclamation_density'] = df[cc].apply(lambda x: (x.count('!') + x.count('\uff01')) / max(len(x), 1))

    # 7 is_random_name
    df['is_random_name'] = df[nc].apply(lambda x: 1 if re.search(r'\d{5,}', x) else 0)

    # 8 engagement_count - Average of recent 20 posts    # --- 特征 8: engagement_count （互动率 - 绝对量版本）---
    def calc_recent_engagement(eng_list):
        if not eng_list or not isinstance(eng_list, list): return 1.0 # 护盾：0互动兜底为1
        
        # 确保列表中全是数字
        try:
            eng_list = [float(x) for x in eng_list]
        except Exception:
            return 1.0 # 护盾
            
        if len(eng_list) == 0: return 1.0 # 护盾
        
        avg_eng = sum(eng_list) / len(eng_list)
        return max(1.0, avg_eng) # 方案A：强制兜底。如果平均互动<1，统一视为1，保护低调素人

    df['engagement_count'] = df.apply(lambda r: calc_recent_engagement(r.get('recent_engagements', [])), axis=1)

    # 9 is_verified
    auth = 'user_authentication'
    df['is_verified'] = df.get(auth, pd.Series([''] * len(df))).astype(str).apply(lambda x: 1 if 'V' in x or '认证' in x else 0)

    # 10 sentiment_score
    df['sentiment_score'] = df[cc].apply(calc_sentiment)


    # 13 topic_diversity (取代旧的urank)
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
        
        # 核心改进：没有带标签的日常帖，每一贴都相当于一个独特的“生活切片”(唯一标签)
        # 用总帖数减去抓取到的标签总数，估算未带标签的帖子量
        untagged_posts = max(0, n_posts - m_tags)
        
        score = (unique_tags + untagged_posts) / n_posts
        return float(min(1.0, score))
        
    df['topic_diversity'] = df.apply(calc_topic_diversity, axis=1)

    # 15 post_interval_variance (Using Standard Deviation so <1 hour math doesn't shrink to microscopic numbers)
    def _calc_variance(times_list):
        if not times_list or len(times_list) < 2:
            return 0.0 # 无法计算，默认0
        try:
            # 转换时间字符串为 datetime
            dts = [pd.to_datetime(t).replace(tzinfo=None) for t in times_list]
            dts.sort()
            # 计算相邻发帖的时间差（小时）
            intervals = [(dts[i+1] - dts[i]).total_seconds() / 3600.0 for i in range(len(dts)-1)]
            # 返回标准差
            return float(np.std(intervals))
        except Exception as e:
            return 0.0
            
    df['post_interval_variance'] = df.get('recent_post_times', pd.Series([[]]*len(df))).apply(_calc_variance)

    # ====== 对数缩放 ======
    for col in ['daily_post_rate', 'post_interval_variance']:
        if col in df.columns:
            df[col] = np.log1p(df[col].clip(lower=0))

    return df
