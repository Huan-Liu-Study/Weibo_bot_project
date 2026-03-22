# -*- coding: utf-8 -*-
"""
统一可疑度评分系统 (v1.8.0)
=========================
供话题检测 (bot_pipeline.py) 和单账号检测 (server.py) 共同调用，
确保同一个账号在任何检测入口下返回一致的可疑度评分。

评分体系:
  最终可疑度 = 0.2 × 规则评分 + 0.8 × 模型概率
  + 红旗否决机制 (触发极端特征时强制拉高)
  + 新闻媒体豁免 (认证媒体账号 ×0.3 衰减)
"""

import joblib
import numpy as np

# ===================== 常量 =====================

FEATURE_COLS = [
    'daily_post_rate', 'human_likeness_score',
    'exclamation_density', 'is_random_name', 'engagement_count', 'is_verified',
    'sentiment_score', 'topic_diversity', 'post_interval_variance'
]

RED_FLAG_MIN_SCORE = 0.55

_OFFICIAL_MEDIA_KEYWORDS = [
    '新闻', '媒体', '报社', '电视台', '日报', '晚报',
    '广播', '通讯社', '新华', '央视', '人民', '环球',
    '纵览', '头条', '党建', '商报',   '播报', '发布', 
    '发布厅', '周刊', '官微', '政务', '电台', '融媒体', '时报'
]

_AUTH_KEYWORDS = ['蓝v', '企业认证', '媒体认证', '政府认证']

# ===================== 核心函数 =====================


def is_official_media(row):
    """
    判断是否为新闻媒体、政务、客户端或企业官方认证账号。
    扫描维度：人工媒体白名单库 (media_store.db) -> 认证类型 -> 简介 -> 昵称。
    """
    # 0. 最高优先级拦截：动态媒体白名单库
    uid = str(row.get('user_id', row.get('id', '')))
    if uid:
        try:
            import media_db
            if media_db.is_in_media_db(uid):
                return True
        except Exception:
            pass

    auth = str(row.get('user_authentication', '')).lower() + str(row.get('verified_reason', '')).lower()
    desc = str(row.get('description', '')).lower()
    name = str(row.get('screen_name', row.get('用户昵称', ''))).lower()
    
    # 1. 强特征：蓝V、企业/政府/媒体等认证标志
    if any(k in auth for k in _AUTH_KEYWORDS):
        return True
        
    # 2. 弱特征池：任何字段命中媒体/官方关键词
    combined_text = auth + " | " + desc + " | " + name
    if any(k in combined_text for k in _OFFICIAL_MEDIA_KEYWORDS):
        return True
        
    return False




def calc_rule_score(row):
    """
    基于规则的加权可疑度计算 (0.0 ~ 1.0)

    权重优先级:
      发帖间隔方差(0.25) > 日均发帖率(0.25) > 互动率(0.25) > 数字名(0.15) > 感叹号(0.10)
    """
    score = 0.0
    total_weight = 0.0

    # ★★★ 发帖间隔标准差 (权重 0.25)
    w = 0.25
    piv = float(row.get('post_interval_variance', 0))
    if piv < 0.41:      sub = 1.0
    elif piv < 1.10:     sub = 0.7
    elif piv < 1.79:     sub = 0.3
    else:                sub = 0.0
    score += w * sub
    total_weight += w

    # ★★★ 日均发帖率 (权重 0.25)
    w = 0.25
    dpr = float(row.get('daily_post_rate', 0))
    if dpr > 3.93:       sub = 1.0
    elif dpr > 3.04:     sub = 0.7
    elif dpr > 2.40:     sub = 0.4
    elif dpr > 1.79:     sub = 0.15
    else:                sub = 0.0
    score += w * sub
    total_weight += w

    # ★★★ 平均互动率 (权重 0.25)
    w = 0.25
    ec = float(row.get('engagement_count', 0))
    if ec == 0:          sub = 1.0
    elif ec < 0.69:      sub = 0.7
    elif ec < 1.6:       sub = 0.3
    else:                sub = 0.0
    score += w * sub
    total_weight += w

    # ★★ 数字乱码名 (权重 0.15)
    w = 0.15
    sub = 1.0 if int(row.get('is_random_name', 0)) == 1 else 0.0
    score += w * sub
    total_weight += w

    # ★ 感叹号密度 (权重 0.10)
    w = 0.10
    ed = float(row.get('exclamation_density', 0))
    if ed > 0.08:        sub = 1.0
    elif ed > 0.04:      sub = 0.5
    else:                sub = 0.0
    score += w * sub
    total_weight += w

    # 加权归一化
    raw_score = score / total_weight if total_weight > 0 else 0.0

    # 新闻媒体认证豁免 (×0.3 衰减)
    if is_official_media(row):
        raw_score *= 0.3

    return round(min(max(raw_score, 0.0), 1.0), 4)


def apply_red_flags(row_score, row):
    """
    红旗否决机制：即使模型整体打分很低，只要关键特征
    触发极端阈值，就强制提升可疑度到 RED_FLAG_MIN_SCORE。
    """
    flags = []

    # 🔴 红旗1: 发帖间隔方差极低
    piv = float(row.get('post_interval_variance', -1))
    if 0 < piv <= 0.69:
        flags.append(f'发帖间隔方差(log)={piv:.4f}≤log1p(1)')

    # 🔴 红旗2: 日均发帖量极高
    dpr = float(row.get('daily_post_rate', 0))
    if dpr >= 3.93:
        flags.append(f'日均发帖(log)={dpr:.2f}≥log1p(50)')

    # 🔴 红旗3: 话题多样性极低
    td = float(row.get('topic_diversity', 0.5))
    if td <= 0.1 and td != 0.5:
        flags.append(f'话题多样性={td:.2f}≤10%')

    if flags:
        return max(row_score, RED_FLAG_MIN_SCORE)
    return row_score


def compute_final_score(features_dict, model_prob, row, model_available=True):
    """
    统一融合评分入口。

    Parameters
    ----------
    features_dict : dict
        包含所有特征列值的字典 (用于规则评分)
    model_prob : float
        模型 predict_proba 的正类概率 (0~1)
    row : dict
        包含 verified_reason 等元数据的原始行 (用于媒体豁免)
    model_available : bool
        若模型加载失败，将仅使用规则分 (Fallback)

    Returns
    -------
    float : 最终可疑度 0.0 ~ 1.0
    """
    rule_score = calc_rule_score(features_dict)

    # 80% 模型 + 20% 规则 (若模型不可用则 100% 规则)
    if model_available:
        fused = 0.2 * rule_score + 0.8 * model_prob
    else:
        fused = rule_score

    # 红旗否决
    fused = apply_red_flags(fused, features_dict)

    # 新闻媒体豁免 (双重保障: 规则内部已做了一次, 融合后再 clip)
    if is_official_media(row):
        fused = min(fused, 0.3)

    return round(min(max(fused, 0.0), 1.0), 4)


def get_model_proba(X):
    """
    加载模型并返回各行的正类概率。

    Parameters
    ----------
    X : pd.DataFrame
        包含 FEATURE_COLS 列的特征矩阵

    Returns
    -------
    (np.ndarray, bool) : (概率数组, 模型是否可用)
    """
    try:
        model = joblib.load('weibo_bot_rf_model.pkl')
        if hasattr(model, 'predict_proba'):
            probs = model.predict_proba(X)
            result = np.array([p[1] if len(p) > 1 else p[0] for p in probs])
        else:
            result = np.clip(model.predict(X), 0, 1)
        return result, True
    except Exception as e:
        print(f"[INFO] 模型推断跳过: {e}")
        return np.full(len(X), 0.5), False
