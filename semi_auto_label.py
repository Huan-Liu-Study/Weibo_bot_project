import pandas as pd
import numpy as np
import joblib
import os
import sys
import io
import asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from label_existing_data import _fetch_all, compute_15_features, _load_cookie

def get_ml_features(df):
    """提取模型所需特征"""
    cols = [
        'follower_friend_ratio', 'daily_post_rate', 'human_likeness_score',
        'exclamation_density', 'is_random_name', 'engagement_rate', 'is_verified',
        'sentiment_score', 'topic_diversity', 'post_interval_variance'
    ]
    for c in cols:
        if c not in df.columns:
            df[c] = 0
    return df[cols].fillna(0)

def main():
    print("=" * 70)
    print("  微博水军半自动标注工具 (Hybrid Active Learning)")
    print("=" * 70)

    pool_file = 'unlabeled_pool.csv'
    if not os.path.exists(pool_file):
        print(f"[ERROR] 找不到大蓄水池 {pool_file}，请先运行 batch_crawler.py")
        return

    df = pd.read_csv(pool_file, encoding='utf-8-sig')
    print(f"[{pool_file}] 发现 {len(df)} 条原始数据")

    # 1. 查询话题列表并要求选择
    topics = df['topic_query'].unique() if 'topic_query' in df.columns else ['未知话题']
    print("\n请选择要进行半自动标注的话题:")
    for i, t in enumerate(topics):
        cnt = len(df[df['topic_query']==t]) if 'topic_query' in df.columns else len(df)
        print(f"  [{i}] {t} ({cnt} 条微博)")
    
    try:
        t_idx = int(input(f"\n选择话题序号 [0-{len(topics)-1}]: ").strip())
        target_topic = topics[t_idx]
    except (ValueError, IndexError):
        print("输入无效退出")
        return
        
    topic_df = df[df['topic_query'] == target_topic].copy()
    unique_uids = topic_df['user_id'].unique()
    print(f"\n>> 选定话题: {target_topic} (共 {len(unique_uids)} 个独立用户)")

    # 2. 补全 API 信息与特征
    print(f"\n[1/4] 获取/更新 这 {len(unique_uids)} 个用户的 API 画像资料...")
    cookie = _load_cookie()
    HEADERS = {'cookie': cookie, 'User-Agent': 'Mozilla/5.0'}
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    results = loop.run_until_complete(_fetch_all(unique_uids, HEADERS))
    loop.close()

    user_map = {r['uid']: r for r in results}
    for field in ['followers_count', 'friends_count', 'statuses_count', 'description', 'avatar_hd', 'recent_post_times', 'recent_engagements', 'recent_topics', 'verified_reason']:
        col_name = 'account_created_at' if field == 'created_at' else field
        topic_df[col_name] = topic_df['user_id'].apply(lambda x: user_map.get(x, {}).get(field, ''))
        
    print("[2/4] 计算 15 维特征...")
    topic_df = compute_15_features(topic_df)

    # 3. 加载已有金标准，防止重复标注
    golden_file = 'golden_testset_labeled.csv'
    labeled_uids = set()
    if os.path.exists(golden_file):
        golden_df = pd.read_csv(golden_file)
        if 'user_id' in golden_df.columns:
            labeled_uids = set(golden_df['user_id'].unique())
            
    unlabeled_uids = [u for u in unique_uids if u not in labeled_uids]
    if not unlabeled_uids:
        print("\n[!] 该话题下的所有用户都已在金标准库中完成标注。")
        return
        
    print(f"[3/4] 过滤已标注数据，剩余 {len(unlabeled_uids)} 个新用户待处理...")
    work_df = topic_df[topic_df['user_id'].isin(unlabeled_uids)].copy()

    # 4. 模型预测
    print("[4/4] 加载上版本模型进行预筛选...")
    has_model = False
    if os.path.exists('weibo_bot_rf_model.pkl'):
        try:
            model = joblib.load('weibo_bot_rf_model.pkl')
            X = get_ml_features(work_df)
            if hasattr(model, 'predict_proba'):
                probs = model.predict_proba(X)
                work_df['model_pred'] = [p[1] if len(p)>1 else p[0] for p in probs]
            else:
                work_df['model_pred'] = model.predict(X).clip(0, 1)
            has_model = True
            print("  模型加载成功，已完成所有未标注数据的可疑度预测。")
        except Exception as e:
            print(f"  模型加载失败: {e}")
            work_df['model_pred'] = 0.5
    else:
        print("  未找到模型，使用中性分数。")
        work_df['model_pred'] = 0.5

    # ==========================
    # 分层与交互标注
    # ==========================
    # 我们按 user_id 汇总一下分数（取该用户发帖中第一条的分数代表，特征是一样的）
    user_scores = []
    for uid in unlabeled_uids:
        first_row = work_df[work_df['user_id'] == uid].iloc[0]
        user_scores.append({
            'uid': uid,
            'score': first_row['model_pred']
        })
        
    # 分流逻辑
    # 如果该话题之前没标过任何人（属于开荒），强制抽取 30% 最具代表性的样本作为种子
    topic_labeled_count = len(golden_df[golden_df['topic_query']==target_topic]) if os.path.exists(golden_file) and 'topic_query' in golden_df.columns else 0
    
    requires_seed = (topic_labeled_count == 0)
    
    if requires_seed:
        print(f"\n{'#'*60}")
        print(f"【⚠️ 种子开荒模式】此话题你在库里还未标注过！")
        print(f"为了让模型学习该领域的独特特征，需要强制抽取 15 个用户进行人工盲打。")
        print(f"完成后，老模型和这些新种子将重新融合训练。")
        print(f"{'#'*60}")
        
        # 均匀抽样 15 个不同分段的（尽早让模型见到全光谱）
        user_scores.sort(key=lambda x: x['score'])
        step = max(1, len(user_scores) // 15)
        review_uids = [u['uid'] for u in user_scores[::step]][:15]
        
    else:
        # 非开荒模式：只复核极度模糊的边界地带
        print(f"\n【🚀 机器辅助模式】此话题已有 {topic_labeled_count} 条你的标注基准。")
        
        auto_human = [u['uid'] for u in user_scores if u['score'] < 0.2]
        auto_bot = [u['uid'] for u in user_scores if u['score'] > 0.8]
        review_uids = [u['uid'] for u in user_scores if 0.2 <= u['score'] <= 0.8]
        
        print(f"  🟢 模型极度信任 (Score < 0.2): {len(auto_human)} 人 -> 自动归为 0档 (不展示)")
        print(f"  🔴 模型极度怀疑 (Score > 0.8): {len(auto_bot)} 人 -> 自动归为 4档 (不展示)")
        print(f"  🟡 模型吃不准   (0.2~0.8):    {len(review_uids)} 人 -> 将展示给你进行抽检")
        
        confirm = input("\n同意将上述高纯度数据自动打标签并在后台合并吗？(y/n): ")
        if confirm.lower() == 'y':
            # 自动打标逻辑
            auto_rows = []
            # 自动好人
            for uid in auto_human:
                user_posts = work_df[work_df['user_id'] == uid]
                for _, row in user_posts.iterrows():
                    d = row.to_dict()
                    d['suspicion_label'] = 0
                    d['suspicion_score'] = 0.0
                    auto_rows.append(d)
            # 自动坏人
            for uid in auto_bot:
                user_posts = work_df[work_df['user_id'] == uid]
                for _, row in user_posts.iterrows():
                    d = row.to_dict()
                    d['suspicion_label'] = 4
                    d['suspicion_score'] = 1.0
                    auto_rows.append(d)
                    
            if auto_rows:
                auto_df = pd.DataFrame(auto_rows)
                golden_df = pd.concat([golden_df, auto_df], ignore_index=True)
                golden_df.to_csv(golden_file, index=False, encoding='utf-8-sig')
                print(f"  [OK] 已成功将 {len(auto_human)+len(auto_bot)} 人的数据自动打标并并入 {golden_file}！")
        else:
            print("  [INFO] 已取消自动打标，仅进入人工复核模式。")

    if not review_uids:
        print("\n没有需要人工复核的数据了！")
        return

    print("\n" + "=" * 60)
    print(f"  开始人工复核 ({len(review_uids)} 人)")
    print("  0=真人 1=大概率真人 2=不确定 3=可疑 4=水军 / q=退出")
    print("=" * 60)

    # 复用之前写的 UI 展示代码
    content_col = '微博正文' if '微博正文' in work_df.columns else [c for c in work_df.columns if '正文' in c or 'text' in c.lower()][0]
    name_col = '用户昵称' if '用户昵称' in work_df.columns else [c for c in work_df.columns if '昵称' in c or 'name' in c.lower()][0]

    manually_labeled_rows = []
    quit_flag = False
    
    for i, uid in enumerate(review_uids):
        if quit_flag: break
        
        user_posts = work_df[work_df['user_id'] == uid]
        row = user_posts.iloc[0]
        model_score = next((u['score'] for u in user_scores if u['uid']==uid), 0.5)

        print(f"\n{'─'*60}")
        print(f"  [{i+1}/{len(review_uids)}] 用户: {row.get(name_col, '未知')}")
        print(f"{'─'*60}")
        
        # 打印 AI 意见
        if has_model:
            ai_opinion = f"🤖 AI初查分数: {model_score:.2f} "
            if model_score > 0.6: ai_opinion += "👈 倾向认为是水军"
            elif model_score < 0.4: ai_opinion += "👈 倾向认为是真人"
            else: ai_opinion += "👈 AI吃不准，请人类裁决，这是盲区！"
            print(ai_opinion)
        
        print(f"  粉丝: {row.get('followers_count',0)} | 关注: {row.get('friends_count',0)} | 总帖: {row.get('statuses_count',0)}")
        v_reason = row.get('verified_reason', '')
        print(f"  认证: {f'【{v_reason}】' if v_reason else '无'}")
        
        desc = str(row.get('description', ''))
        print(f"  简介: {desc[:80] if desc else '(空)'}")

        print(f"\n  ── 近期抓取的 {len(user_posts)} 条本话题微博 ──")
        for j, (_, post) in enumerate(user_posts.iterrows()):
            text = str(post.get(content_col, '')).replace('\n', ' ')
            print(f"    [{j+1}] \"{text[:100]}...\"" if len(text)>100 else f"    [{j+1}] \"{text}\"")

        var_score = float(row.get('post_interval_variance', 0))
        dpr = float(row.get('daily_post_rate', 0))
        er = float(row.get('engagement_rate', 0))
        ffr = float(row.get('follower_friend_ratio', 0))
        followers = int(row.get('followers_count', 0))
        
        if er == 0: er_display = "⚠️ 0 (零互动/全转发)"
        elif er < 0.001: er_display = f"⚠️ 万分之{er*10000:.1f} (极低)"
        elif er < 0.01: er_display = f"千分之{er*1000:.1f} (偏低)"
        else: er_display = f"✓ {er*100:.2f}% (正常)"
        
        if ffr >= 1: ffr_display = f"✓ {ffr:.1f}:1 (正常)"
        elif ffr > 0: 
            if (1/ffr) > 5: ffr_display = f"⚠️ 1:{1/ffr:.1f} (关远大于粉，高度可疑)"
            else: ffr_display = f"1:{1/ffr:.1f} (关略大于粉)"
        else: ffr_display = "⚠️ 0粉 (极度可疑)"

        dpr_level = "极高" if dpr > 50 else "偏高" if dpr > 20 else "中等" if dpr > 5 else "正常"
        var_level = "极其规律" if var_score < 0.5 else "比较规律" if var_score < 2 else "一般" if var_score < 5 else "随机"
        td_val = float(row.get('topic_diversity', 0))
        hl_val = float(row.get('human_likeness_score', 0))

        print(f"\n  ┌─ 关键特征 {'─'*40}")
        print(f"  │ 发帖间隔方差: {var_score:.2f} 小时 ({var_level}) | 日均发帖: {dpr:.1f} 帖/天 ({dpr_level})")
        print(f"  │ 平均互动率:   {er_display} (均互动{er*followers:.0f}) | 粉关比: {ffr_display}")
        print(f"  │ 话题多样性:   {td_val*100:.0f}% (越低越像刷榜机器) | 语义拟人度: {hl_val*100:.0f}% (越高越像真人)")
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
                choice = input("\n  您的判断 [0=真人 1=大概率真人 2=不确定 3=可疑 4=水军 / q=退出]: ").strip()
            except EOFError:
                choice = 'q'
            if choice in ['0', '1', '2', '3', '4']:
                raw_label = int(choice)
                for _, post_row in user_posts.iterrows():
                    d = post_row.to_dict()
                    d['suspicion_label'] = raw_label
                    d['suspicion_score'] = round(raw_label / 4.0, 4)
                    manually_labeled_rows.append(d)
                break
            elif choice.lower() == 'q':
                quit_flag = True
                break
            else:
                print("  [!] 输入无效")

    if manually_labeled_rows:
        new_df = pd.DataFrame(manually_labeled_rows)
        # 附加到文件尾部
        if os.path.exists(golden_file):
            old_golden = pd.read_csv(golden_file, encoding='utf-8-sig')
            final_df = pd.concat([old_golden, new_df], ignore_index=True)
        else:
            final_df = new_df
            
        final_df.to_csv(golden_file, index=False, encoding='utf-8-sig')
        print(f"\n[OK] 保存成功！{len(manually_labeled_rows)} 条你人工复核的数据已写入 {golden_file}")
        
        # 自动触发模型重新训练
        from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
        from sklearn.model_selection import KFold, cross_val_score
        
        if len(final_df) >= 10:
            print(f"\n🚀 正在根据最新融合的数据集（共 {len(final_df)} 条）重新训练机器模型...")
            feature_cols = [
                'follower_friend_ratio', 'daily_post_rate', 'human_likeness_score',
                'exclamation_density', 'is_random_name', 'engagement_rate', 'is_verified',
                'sentiment_score', 'topic_diversity', 'post_interval_variance'
            ]
            for c in feature_cols:
                if c not in final_df.columns: final_df[c] = 0.0
                
            X = final_df[feature_cols].fillna(0)
            y = final_df['suspicion_score']
            
            # 回归模型
            rfr = RandomForestRegressor(n_estimators=200, random_state=42, max_depth=8)
            rfr.fit(X, y)
            joblib.dump(rfr, 'weibo_bot_rf_model.pkl')
            print(f"  [√] 回归核心模型已更新: weibo_bot_rf_model.pkl")
            
            # 分类模型(二值)
            y_binary = (y >= 0.5).astype(int)
            if y_binary.nunique() >= 2:
                rfc = RandomForestClassifier(n_estimators=200, random_state=42, max_depth=8)
                rfc.fit(X, y_binary)
                joblib.dump(rfc, 'weibo_bot_rf_classifier.pkl')
                print(f"  [√] 二值分类器已更新: weibo_bot_rf_classifier.pkl")
                
            print("\n>>> 模型进化完成！下一次筛选将变得更精准。")
        else:
            print("\n>>> 样本总数不足 10 条，暂跳过模型重练。")
    else:
        print("\n未进行任何人肉打标。")

if __name__ == "__main__":
    main()
