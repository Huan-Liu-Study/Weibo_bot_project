from scoring import is_official_media

def generate_reasons(features, score, user_info):
    """根据特征值生成人类可读的判定理由"""
    reasons = []

    # 优先检查新闻媒体豁免
    row_check = {
        'description': user_info.get('description', ''),
        'verified_reason': user_info.get('verified_reason', ''),
        'user_authentication': user_info.get('user_authentication', ''),
        'screen_name': user_info.get('screen_name', '')
    }
    
    if is_official_media(row_check):
        reasons.append({
            "level": "low", 
            "text": "✅ 系统识其为媒体/官方机构：已执行豁免算法，大幅降低评分权重，降低误报。"
        })

    piv = features.get('post_interval_variance', 0)
    if piv < 0.69:
        reasons.append({"level": "high", "is_red_flag": True, "text": f"🚩 红旗预警：发帖间隔极其机械化（方差={piv:.2f}），已触发系统自动拦截机制"})
    elif piv < 1.5:
        reasons.append({"level": "medium", "text": f"🟡 发帖间隔较为规律（方差={piv:.2f}），有一定可疑度"})
    else:
        reasons.append({"level": "low", "text": f"低危：发帖间隔较随机（方差={piv:.2f}）"})

    dpr = features.get('daily_post_rate', 0)
    if dpr >= 3.93:
        reasons.append({"level": "high", "is_red_flag": True, "text": f"🚩 红旗预警：日均发帖量极高（log值={dpr:.2f}），超出人类极限，判定为机器代发"})
    elif dpr > 2.4:
        reasons.append({"level": "medium", "text": f"🟡 日均发帖率偏高（log值={dpr:.2f}）"})
    else:
        reasons.append({"level": "low", "text": f"🟢 发帖频率正常（log值={dpr:.2f}）"})

    ec = features.get('engagement_count', 0)
    if ec <= 1.0:
        reasons.append({"level": "high", "text": f"🔴 平均互动量极低（{ec:.1f}），发了帖子无人响应，典型水军特征"})
    elif ec < 5.0:
        reasons.append({"level": "medium", "text": f"🟡 平均互动量偏低（{ec:.1f}）"})
    else:
        reasons.append({"level": "low", "text": f"🟢 互动量健康（{ec:.1f}），有正常的社交互动"})

    hl = features.get('human_likeness_score', 0)
    if hl < 0.2:
        reasons.append({"level": "high", "text": f"🔴 文本语义拟人度极低（{hl:.2f}），内容像模板生成"})
    elif hl > 0.5:
        reasons.append({"level": "low", "text": f"🟢 文本内容自然丰富（拟人度={hl:.2f}），像真人撰写"})

    td = features.get('topic_diversity', 0)
    if td <= 0.1:
        reasons.append({"level": "high", "is_red_flag": True, "text": f"🚩 红旗预警：话题分布极其狭隘（多样性={td:.2f}），明显属于工业化刷榜脚本"})
    elif td < 0.2:
        reasons.append({"level": "high", "text": f"🔴 话题多样性极低（{td:.2f}），疑似长期刷单一话题"})
    elif td > 0.7:
        reasons.append({"level": "low", "text": f"低危：话题涉猎广泛（多样性={td:.2f}）"})

    if features.get('is_random_name', 0) == 1:
        reasons.append({"level": "high", "text": "🔴 乱码昵称：识别为系统随机生成的数字乱码，符合批量注册特征"})

    ed = features.get('exclamation_density', 0)
    if ed > 0.1:
        reasons.append({"level": "medium", "text": f"🟡 文本感叹号密度极高（{ed*100:.1f}%），带有强烈情绪诱导特征"})

    ss = features.get('sentiment_score', 0.5)
    if ss < 0.2:
        reasons.append({"level": "medium", "text": f"🟡 情感倾向极负面（{ss:.2f}），可能涉及负面舆论引导"})
    elif ss > 0.8:
        reasons.append({"level": "low", "text": f"🟢 情感倾向积极正面（{ss:.2f}）"})

    vr = user_info.get('verified_reason', '')
    if vr:
        reasons.append({"level": "low", "text": f"🟢 已通过微博认证：{vr}"})

    return reasons
