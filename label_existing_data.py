"""
label_existing_data.py
========================
对已爬取的 CSV 数据进行人工标注，无需重新爬虫。
标注完成后自动计算 14 维特征并训练模型。
"""
import sys
import io
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np
import re
import os
import asyncio
import aiohttp
import joblib
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import cross_val_score, StratifiedKFold, KFold


# ===================== Cookie =====================

def _load_cookie():
    with open('weibo-search/weibo/settings.py', 'r', encoding='utf-8') as f:
        content = f.read()
    match = re.search(r"'cookie'\s*:\s*'([^']+)'", content)
    return match.group(1) if match else ''


# ===================== 异步获取用户画像 =====================

async def _fetch_one(session, uid, headers):
    # 1. 获取基本画像
    url_info = f'https://weibo.com/ajax/profile/info?custom={uid}'
    h = headers.copy()
    h['Referer'] = f'https://weibo.com/u/{uid}'
    h['Accept'] = 'application/json, text/plain, */*'
    result = {'uid': uid, 'followers_count': 0, 'friends_count': 0,
              'statuses_count': 0, 'created_at': '', 'description': '',
              'avatar_hd': '', 'recent_post_times': [],
              'recent_engagements': [], 'recent_topics': [], 'verified_reason': ''}
    try:
        await asyncio.sleep(0.15)
        async with session.get(url_info, headers=h, timeout=8) as resp:
            if resp.status == 200:
                data = await resp.json()
                u = data.get('data', {}).get('user', {})
                if u:
                    for k in result:
                        if k not in ['uid', 'recent_post_times']:
                            result[k] = u.get(k, result[k])
    except Exception as e:
        print(f"  [!] user info {uid}: {e}")

    # 2. 获取近期发帖列表 (用于时序特征)
    url_timeline = f'https://weibo.com/ajax/statuses/mymblog?uid={uid}&page=1&feature=0'
    try:
        await asyncio.sleep(0.15)
        async with session.get(url_timeline, headers=h, timeout=8) as resp:
            if resp.status == 200:
                data = await resp.json()
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
                        
                        if is_own_post and not is_retweet:
                            eng = p.get('reposts_count', 0) + p.get('comments_count', 0) + p.get('attitudes_count', 0)
                            eng_list.append(eng)
                            
                            # 提取特征：话题多样性
                            # 寻找 #话题# 格式的内容
                            text = p.get('text_raw', p.get('text', ''))
                            import re
                            found_topics = re.findall(r'#([^#]+)#', text)
                            if found_topics:
                                topics_list.extend(found_topics)
                    
                    result['recent_engagements'] = eng_list
                    result['recent_topics'] = topics_list
    except Exception as e:
        print(f"  [!] user timeline {uid}: {e}")

    return result

async def _fetch_all(uids, headers):
    async with aiohttp.ClientSession() as s:
        return await asyncio.gather(*[_fetch_one(s, uid, headers) for uid in uids])


# ===================== 特征计算 =====================

def compute_15_features(df):
    from snownlp import SnowNLP

    cc = '微博正文' if '微博正文' in df.columns else 'text'
    nc = '用户昵称' if '用户昵称' in df.columns else 'screen_name'
    df[cc] = df[cc].astype(str).fillna('')
    df[nc] = df[nc].astype(str).fillna('')

    for c in ['followers_count', 'friends_count', 'statuses_count']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)

    # 1 follower_friend_ratio
    df['follower_friend_ratio'] = df.apply(
        lambda r: r['followers_count'] / r['friends_count'] if r['friends_count'] > 0 else float(r['followers_count']), axis=1)

    # ====== 统一解析：将 CSV 中存储的字符串格式列表还原为 Python list ======
    import ast
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
                return float(len(times_list))
            return len(times_list) / span_days
        except: return 0.0
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

    # 5 link_count
    df['link_count'] = df[cc].apply(lambda x: len(re.findall(r'https?://', x)))

    # 6 is_default_avatar
    av = df.get('avatar_hd', df.get('头像url', pd.Series([''] * len(df)))).astype(str)
    df['is_default_avatar'] = av.apply(lambda x: 1 if 'default' in x.lower() or ('tvax' not in x and 'tva' not in x and len(x) > 5) else 0)

    # 7 is_random_name
    df['is_random_name'] = df[nc].apply(lambda x: 1 if re.search(r'\d{5,}', x) else 0)

    # 8 engagement_rate - Average of recent 20 posts    # --- 特征 8: engagement_rate （互动率）---
    def calc_recent_engagement(eng_list, followers):
        if followers <= 0: return 0.0
        
        # 处理可能来自CSV的字符串格式列表 (e.g., "[1, 2, 3]")
        if isinstance(eng_list, str):
            try:
                import ast
                eng_list = ast.literal_eval(eng_list)
            except Exception:
                eng_list = []
                
        if not eng_list or not isinstance(eng_list, list): return 0.0
        
        # 确保列表中全是数字
        try:
            eng_list = [float(x) for x in eng_list]
        except Exception:
            return 0.0
            
        avg_eng = sum(eng_list) / len(eng_list)
        return avg_eng / followers

    eng_list_col = df.get('recent_engagements', pd.Series([[]]*len(df)))
    df['engagement_rate'] = df.apply(lambda r: calc_recent_engagement(r.get('recent_engagements', []), r['followers_count']), axis=1)

    # 9 is_verified
    auth = 'user_authentication'
    df['is_verified'] = df.get(auth, pd.Series([''] * len(df))).astype(str).apply(lambda x: 1 if 'V' in x or '认证' in x else 0)

    # 10 sentiment_score
    def _sent(text):
        clean = re.sub(r"http\S+", "", text).strip()
        if not clean: return 0.5
        # SnowNLP 朴素贝叶斯遇到长文本会导致概率连乘极化，永远等于 1.0 或 0.0
        # 所以截取前 100 个字符进行情感判断更准
        clean = clean[:100]
        try: 
            score = SnowNLP(clean).sentiments
            return round(score, 4)
        except: return 0.5
    df['sentiment_score'] = df[cc].apply(_sent)

    # 11 post_hour
    tc = '发布时间' if '发布时间' in df.columns else 'created_at'
    df['post_hour'] = df.get(tc, pd.Series([''] * len(df))).apply(
        lambda t: pd.to_datetime(str(t)).hour if pd.notna(t) and str(t) != 'nan' else 12)

    # 12 desc_len
    df['desc_len'] = df.get('description', pd.Series([''] * len(df))).astype(str).apply(len)

    # 13 topic_diversity (取代旧的urank)
    def calc_topic_diversity(row):
        topics = row.get('recent_topics', [])
        times_list = row.get('recent_post_times', [])
        if not isinstance(times_list, list) or len(times_list) == 0:
            return 0.5  # 无数据时返回中性值
        if not isinstance(topics, list) or len(topics) == 0:
            return 0.5  # 没有话题标签 → 可能是真人日常帖，给中性值而非0
        return len(set(topics)) / len(times_list)
        
    df['topic_diversity'] = df.apply(calc_topic_diversity, axis=1)

    # 14 topic_count
    tpc = '话题' if '话题' in df.columns else 'topics'
    df['topic_count'] = df.get(tpc, pd.Series([''] * len(df))).astype(str).apply(
        lambda x: len([t for t in x.split(',') if t.strip()]) if x and x != 'nan' else 0)

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

    # ====== 对数缩放：压缩极端范围特征，让模型公平学习所有维度 ======
    for col in ['follower_friend_ratio', 'daily_post_rate', 'post_interval_variance']:
        if col in df.columns:
            df[col] = np.log1p(df[col].clip(lower=0))

    return df


# ===================== MAIN =====================

def main():
    print("=" * 60)
    print("  微博水军标注工具 v2 (离线模式)")
    print("=" * 60)

    csv_path = 'weibo-search/结果文件/中东局势彻底失控/中东局势彻底失控.csv'
    if not os.path.exists(csv_path):
        print(f"[ERROR] 未找到数据文件: {csv_path}")
        return

    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    # 处理 GBK 乱码列名
    col_map = {}
    for c in df.columns:
        if 'id' == c or c.startswith('user_') or c.startswith('retweet') or c == 'ip' or c == 'bid':
            continue
        if not any(ord(ch) > 127 and ord(ch) < 0x4E00 for ch in c):
            continue
        # 可能是乱码列
    print(f"  加载了 {len(df)} 条微博数据")

    # 获取用户画像
    print("\n  从 API 获取用户画像（粉丝数、简介等）...")
    cookie = _load_cookie()
    HEADERS = {'cookie': cookie, 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    uids = df['user_id'].unique()
    print(f"  共 {len(uids)} 个独立用户")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    results = loop.run_until_complete(_fetch_all(uids, HEADERS))
    loop.close()

    user_map = {r['uid']: r for r in results}
    for field in ['followers_count', 'friends_count', 'statuses_count', 'description', 'avatar_hd', 'recent_post_times', 'recent_engagements', 'recent_topics', 'verified_reason']:
        col_name = 'account_created_at' if field == 'created_at' else field
        df[col_name] = df['user_id'].apply(lambda x: user_map.get(x, {}).get(field, ''))

    # 把 API 返回的 created_at 删除了，因为现在 API 不返回 created_at，不能覆盖 CSV 里的原数据

    ok = sum(1 for r in results if r.get('urank', 0) > 0 or r.get('description', ''))
    print(f"  [OK] {ok}/{len(uids)} 个用户画像获取成功")
    
    # 诊断：打印前 3 个用户的发帖数量，看看是否拉取到了时序数据
    for i, r in enumerate(results[:3]):
        posts_len = len(r.get('recent_post_times', []))
        print(f"  [DEBUG] UID {r['uid']} 获取到 {posts_len} 条近期动态。")

    # 计算特征
    print("\n  计算 15 维特征（含时序和情感分析，约 30 秒）...")
    df = compute_15_features(df)

    # 开始标注 — 按用户去重，每个用户只标注一次
    print("\n" + "=" * 60)
    print("  开始人工标注 (5 档可疑度评分)")
    print("  0 = 确定真人    1 = 大概率真人    2 = 不确定")
    print("  3 = 比较可疑    4 = 几乎确定水军")
    print("  q = 保存退出")
    print("  (💡注意: 新闻媒体账号发帖频率极高、互动率低，形似机器，但请标为 0 或 1)")
    print("=" * 60)

    # 解决列名兼容
    content_col = '微博正文' if '微博正文' in df.columns else [c for c in df.columns if '正文' in c or 'text' in c.lower()][0] if any('正文' in c or 'text' in c.lower() for c in df.columns) else df.columns[4]
    name_col = '用户昵称' if '用户昵称' in df.columns else [c for c in df.columns if '昵称' in c or 'name' in c.lower()][0] if any('昵称' in c or 'name' in c.lower() for c in df.columns) else df.columns[3]

    # ★ 核心改动：按 user_id 分组，每个用户只标注一次
    all_unique_uids = df['user_id'].unique()
    
    # 过滤掉已经标注过的用户
    out_path = 'golden_testset_labeled.csv'
    labeled_uids = set()
    if os.path.exists(out_path):
        try:
            existing_df = pd.read_csv(out_path, encoding='utf-8-sig')
            if 'user_id' in existing_df.columns:
                labeled_uids = set(existing_df['user_id'].unique())
        except:
            pass
            
    unique_uids = [u for u in all_unique_uids if u not in labeled_uids]
    
    if not unique_uids:
        print(f"\n  [OK] 数据集中所有 {len(all_unique_uids)} 个用户均已在 {out_path} 中标注完毕！无需重复标注。\n")
        return

    print(f"\n  共 {len(unique_uids)} 个新用户待标注 (原始 {len(df)} 条微博去重，跳过已标注 {len(labeled_uids)} 人)\n")

    labeled_rows = []
    quit_flag = False
    for i, uid in enumerate(unique_uids):
        if quit_flag:
            break

        user_posts = df[df['user_id'] == uid]
        row = user_posts.iloc[0]  # 取第一条作为代表行（特征值相同）

        print(f"\n{'─'*60}")
        print(f"  [{i+1}/{len(unique_uids)}] 用户: {row.get(name_col, '未知')}")
        print(f"{'─'*60}")
        print(f"  粉丝: {row.get('followers_count',0)} | 关注: {row.get('friends_count',0)} | 总帖: {row.get('statuses_count',0)}")
        
        v_reason = row.get('verified_reason', '')
        v_display = f"【{v_reason}】" if v_reason else "无"
        print(f"  认证: {v_display}")
        
        desc = str(row.get('description', ''))
        print(f"  简介: {desc[:80] if desc else '(空)'}")

        # 显示该用户在本次话题下发的所有微博
        print(f"\n  ── 本话题下的 {len(user_posts)} 条微博 ──")
        for j, (_, post) in enumerate(user_posts.iterrows()):
            text = str(post.get(content_col, '')).replace('\n', ' ')
            if len(text) > 100:
                text = text[:100] + "..."
            print(f"    [{j+1}] \"{text}\"")

        # 显示关键特征（人类可读格式）
        var_score = float(row.get('post_interval_variance', 0))
        dpr = float(row.get('daily_post_rate', 0))
        er = float(row.get('engagement_rate', 0))
        ffr = float(row.get('follower_friend_ratio', 0))
        followers = int(row.get('followers_count', 0))
        
        # 互动率转为人类可读格式
        if er == 0:
            er_display = "⚠️ 0 (零互动/全转发)"
        elif er < 0.001:
            er_display = f"⚠️ 万分之{er*10000:.1f} (极低)"
        elif er < 0.01:
            er_display = f"千分之{er*1000:.1f} (偏低)"
        else:
            er_display = f"✓ {er*100:.2f}% (正常)"
        
        # 粉关比转为 X:1 格式
        if ffr >= 1:
            ffr_display = f"✓ {ffr:.1f}:1 (正常)"
        elif ffr > 0:
            if (1/ffr) > 5:
                ffr_display = f"⚠️ 1:{1/ffr:.1f} (关远大于粉，高度可疑)"
            else:
                ffr_display = f"1:{1/ffr:.1f} (关略大于粉)"
        else:
            ffr_display = "⚠️ 0粉 (极度可疑)"

        # 日均发帖率分级
        if dpr > 50:    dpr_level = "⚠️ 极高（疑似自动化）"
        elif dpr > 20:  dpr_level = "⚠️ 偏高"
        elif dpr > 5:   dpr_level = "? 中等"
        else:           dpr_level = "✓ 正常"
        
        dpr_note = " (基于近20条帖子)"
        
        # 发帖间隔解读
        if var_score < 0.5:     var_level = "⚠️ 极其规律（像定时任务）"
        elif var_score < 2:     var_level = "⚠️ 比较规律"
        elif var_score < 5:     var_level = "? 一般"
        else:                   var_level = "✓ 随机（像真人）"
        
        hl_val = float(row.get('human_likeness_score', 0))

        print(f"\n  ┌─ 关键特征 {'─'*40}")
        print(f"  │ ★★★ 发帖间隔标准差: {var_score:.2f} 小时  {var_level}")
        print(f"  │ ★★★ 日均发帖率:     {dpr:.1f} 帖/天  {dpr_level}{dpr_note}")
        print(f"  │ ★★★ 互动率:         {er_display}  (均互动{er*followers:.0f}/粉丝{followers})")
        print(f"  │ ★★  话题多样性:     {td_val*100:.0f}% (越低越像长期刷榜机器)")
        print(f"  │ ★★  语义拟人度:     {hl_val*100:.0f}% (越高越像真人)")
        print(f"  │ ★   粉关比:         {ffr_display}")
        print(f"  │     情感极性:       {row.get('sentiment_score',0.5):.2f}  ({'偏正面' if row.get('sentiment_score',0.5) > 0.6 else '偏负面' if row.get('sentiment_score',0.5) < 0.4 else '中性'})")
        print(f"  └{'─'*50}")

        # 🔴 红旗否决提示
        red_flags = []
        if 0 < var_score <= 1:
            red_flags.append(f'发帖方差={var_score:.2f}<=1 (极度规律)')
        if dpr >= 50:
            red_flags.append(f'日均发帖={dpr:.0f}>=50 (疑似自动化)')
        if td_val <= 0.1 and td_val != 0.5:
            red_flags.append(f'话题多样性={td_val*100:.0f}%<=10% (疑似刷榜)')
        if red_flags:
            print(f"  🚩 红旗预警: {' | '.join(red_flags)}")

        while True:
            try:
                choice = input("  可疑度 [0=真人 1=大概率真人 2=不确定 3=可疑 4=水军 / q=退出]: ").strip()
            except EOFError:
                choice = 'q'
            if choice in ['0', '1', '2', '3', '4']:
                # 为该用户的所有帖子都打上同样的标签
                raw_label = int(choice)
                for _, post_row in user_posts.iterrows():
                    row_dict = post_row.to_dict()
                    row_dict['suspicion_label'] = raw_label
                    row_dict['suspicion_score'] = round(raw_label / 4.0, 4)
                    labeled_rows.append(row_dict)
                tier_names = ['确定真人', '大概率真人', '不确定', '比较可疑', '确定水军']
                print(f"  -> [{raw_label}/4] {tier_names[raw_label]} (归一化: {raw_label/4.0:.2f}) ×{len(user_posts)}条")
                break
            elif choice.lower() == 'q':
                quit_flag = True
                break
            else:
                print("  [!] 请输入 0~4 或 q")

    if labeled_rows:
        result_df = pd.DataFrame(labeled_rows)
        out_path = 'golden_testset_labeled.csv'
        
        # ⚠️ 修复：不要覆盖全量的旧数据！应该加上去。
        if os.path.exists(out_path):
            try:
                old_df = pd.read_csv(out_path, encoding='utf-8-sig')
                final_df = pd.concat([old_df, result_df], ignore_index=True)
            except:
                final_df = result_df
        else:
            final_df = result_df
            
        final_df.to_csv(out_path, index=False, encoding='utf-8-sig')

        # 统计各档分布
        tier_names = ['确定真人(0)', '大概率真人(1)', '不确定(2)', '比较可疑(3)', '确定水军(4)']
        print(f"\n{'='*60}")
        print(f"  本次标注！共 {len(labeled_rows)} 条")
        for t in range(5):
            cnt = sum(1 for r in labeled_rows if r['suspicion_label'] == t)
            if cnt > 0:
                print(f"  本次 {tier_names[t]}: {cnt} 条")
        print(f"  总库体积达到: {len(final_df)} 条，保存至: {out_path}")

        # 训练回归模型 (预测连续可疑度) 必须使用全量库 final_df，而不是刚才标注的十几条 result_df
        if len(final_df) >= 10:
            print(f"\n  正在训练 RandomForest 回归模型 (预测连续可疑度)...")
            feature_cols = [
                'follower_friend_ratio', 'daily_post_rate', 'human_likeness_score',
                'exclamation_density', 'is_random_name', 'engagement_rate', 'is_verified',
                'sentiment_score', 'topic_diversity', 'post_interval_variance'
            ]
            
            # 确保老数据里也有 topic_diversity，没有的补全
            for c in feature_cols:
                if c not in final_df.columns:
                    final_df[c] = 0.0

            X = final_df[feature_cols].fillna(0)
            y = final_df['suspicion_score']  # 0.0 ~ 1.0 连续值

            # 回归模型
            rfr = RandomForestRegressor(n_estimators=200, random_state=42, max_depth=8)
            cv = KFold(n_splits=min(5, len(final_df)), shuffle=True, random_state=42)
            mae_scores = cross_val_score(rfr, X, y, cv=cv, scoring='neg_mean_absolute_error')
            r2_scores = cross_val_score(rfr, X, y, cv=cv, scoring='r2')
            print(f"  交叉验证 MAE: {-mae_scores.mean():.4f} (越小越好)")
            print(f"  交叉验证 R²:  {r2_scores.mean():.4f} (越接近1越好)")

            rfr.fit(X, y)
            model_path = 'weibo_bot_rf_model.pkl'
            joblib.dump(rfr, model_path)
            print(f"  回归模型已保存: {model_path}")

            importances = pd.Series(rfr.feature_importances_, index=feature_cols).sort_values(ascending=False)
            print(f"\n  特征重要性 Top 5:")
            for feat, imp in importances.head(5).items():
                print(f"    {feat}: {imp:.4f}")

            # 同时训练一个分类器作为备用 (用于只需要 0/1 判定的场景)
            # 将 suspicion_score >= 0.5 视为水军
            y_binary = (y >= 0.5).astype(int)
            if y_binary.nunique() >= 2:
                rfc = RandomForestClassifier(n_estimators=200, random_state=42, max_depth=8)
                rfc.fit(X, y_binary)
                joblib.dump(rfc, 'weibo_bot_rf_classifier.pkl')
                print(f"  备用分类器已保存: weibo_bot_rf_classifier.pkl")
        else:
            print("\n  [!] 样本不足 10 条，暂不训练模型")

    print(f"\n{'='*60}")


if __name__ == '__main__':
    main()
