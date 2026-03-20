"""
label_cli.py
========================
对已爬取的 CSV 数据进行人工标注，无需重新爬虫。
标注完成后自动计算特征并训练模型。
"""
import sys
import io
import pandas as pd
import numpy as np
import os
import asyncio
import joblib
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import cross_val_score, StratifiedKFold, KFold

from features import compute_model_features
from weibo_api import fetch_all_users_info
from config import load_cookie

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def main():
    print("=" * 60)
    print("  微博水军标注工具 v3 (离线模式)")
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
    cookie = load_cookie()
    HEADERS = {'cookie': cookie, 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    uids = df['user_id'].unique()
    print(f"  共 {len(uids)} 个独立用户")

    try:
        results = asyncio.run(fetch_all_users_info(uids, HEADERS))
    except Exception as e:
        print(f"Fetch failed: {e}")
        results = []

    user_map = {r['uid']: r for r in results}
    for field in ['followers_count', 'friends_count', 'statuses_count', 'description', 'avatar_hd', 'recent_post_times', 'recent_engagements', 'recent_topics', 'verified_reason']:
        col_name = 'account_created_at' if field == 'created_at' else field
        df[col_name] = df['user_id'].apply(lambda x: user_map.get(x, {}).get(field, ''))

    ok = sum(1 for r in results if r.get('urank', 0) > 0 or r.get('description', ''))
    print(f"  [OK] {ok}/{len(uids)} 个用户画像获取成功")
    
    # 诊断
    for i, r in enumerate(results[:3]):
        posts_len = len(r.get('recent_post_times', []))
        print(f"  [DEBUG] UID {r['uid']} 获取到 {posts_len} 条近期动态。")

    # 计算特征
    print("\n  计算 9 维核心模型特征...")
    df = compute_model_features(df)

    # 开始标注 — 按用户去重，每个用户只标注一次
    print("\n" + "=" * 60)
    print("  开始人工标注 (5 档可疑度评分)")
    print("  0 = 确定真人    1 = 大概率真人    2 = 不确定")
    print("  3 = 比较可疑    4 = 几乎确定水军")
    print("  q = 保存退出")
    print("  (💡注意: 新闻媒体账号发帖频率极高、互动率低，形似机器，但请标为 0 或 1)")
    print("=" * 60)

    content_col = '微博正文' if '微博正文' in df.columns else [c for c in df.columns if '正文' in c or 'text' in c.lower()][0] if any('正文' in c or 'text' in c.lower() for c in df.columns) else df.columns[4]
    name_col = '用户昵称' if '用户昵称' in df.columns else [c for c in df.columns if '昵称' in c or 'name' in c.lower()][0] if any('昵称' in c or 'name' in c.lower() for c in df.columns) else df.columns[3]

    all_unique_uids = df['user_id'].unique()
    
    out_path = 'golden_testset_labeled.csv'
    labeled_uids = set()
    if os.path.exists(out_path):
        try:
            existing_df = pd.read_csv(out_path, encoding='utf-8-sig')
            if 'user_id' in existing_df.columns:
                labeled_uids = set(existing_df['user_id'].unique())
        except Exception:
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
        row = user_posts.iloc[0]

        print(f"\n{'─'*60}")
        print(f"  [{i+1}/{len(unique_uids)}] 用户: {row.get(name_col, '未知')}")
        print(f"{'─'*60}")
        print(f"  粉丝: {row.get('followers_count',0)} | 关注: {row.get('friends_count',0)} | 总帖: {row.get('statuses_count',0)}")
        
        v_reason = row.get('verified_reason', '')
        v_display = f"【{v_reason}】" if v_reason else "无"
        print(f"  认证: {v_display}")
        
        desc = str(row.get('description', ''))
        print(f"  简介: {desc[:80] if desc else '(空)'}")

        print(f"\n  ── 本话题下的 {len(user_posts)} 条微博 ──")
        for j, (_, post) in enumerate(user_posts.iterrows()):
            text = str(post.get(content_col, '')).replace('\n', ' ')
            if len(text) > 100:
                text = text[:100] + "..."
            print(f"    [{j+1}] \"{text}\"")

        var_score = float(row.get('post_interval_variance', 0))
        dpr = float(row.get('daily_post_rate', 0))
        er = float(row.get('engagement_count', 0))
        ffr = float(row.get('follower_friend_ratio', 0))
        followers = int(row.get('followers_count', 0))
        
        if er == 0:
            er_display = "⚠️ 0 (零互动/全转发)"
        elif er < 0.001:
            er_display = f"⚠️ 万分之{er*10000:.1f} (极低)"
        elif er < 0.01:
            er_display = f"千分之{er*1000:.1f} (偏低)"
        else:
            er_display = f"✓ {er*100:.2f}% (正常)"
        
        if ffr >= 1:
            ffr_display = f"✓ {ffr:.1f}:1 (正常)"
        elif ffr > 0:
            if (1/ffr) > 5:
                ffr_display = f"⚠️ 1:{1/ffr:.1f} (关远大于粉，高度可疑)"
            else:
                ffr_display = f"1:{1/ffr:.1f} (关略大于粉)"
        else:
            ffr_display = "⚠️ 0粉 (极度可疑)"

        if dpr > 50:    dpr_level = "⚠️ 极高（疑似自动化）"
        elif dpr > 20:  dpr_level = "⚠️ 偏高"
        elif dpr > 5:   dpr_level = "? 中等"
        else:           dpr_level = "✓ 正常"
        
        dpr_note = " (基于近20条帖子)"
        
        if var_score < 0.5:     var_level = "⚠️ 极其规律（像定时任务）"
        elif var_score < 2:     var_level = "⚠️ 比较规律"
        elif var_score < 5:     var_level = "? 一般"
        else:                   var_level = "✓ 随机（像真人）"
        
        print(f"\n  ┌─ 关键特征 {'─'*40}")
        print(f"  │ ★★★ 发帖间隔标准差: {var_score:.2f} 小时  {var_level}")
        print(f"  │ ★★★ 日均发帖率:     {dpr:.1f} 帖/天  {dpr_level}{dpr_note}")
        print(f"  │ ★★★ 互动率:         {er_display}  (均互动{er*followers:.0f}/粉丝{followers})")
        
        td_val = float(row.get('topic_diversity', 0.5))
        hl_val = float(row.get('human_likeness_score', 0))
        
        print(f"  │ ★★  话题多样性:     {td_val*100:.0f}% (越低越像长期刷榜机器)")
        print(f"  │ ★★  语义拟人度:     {hl_val*100:.0f}% (越高越像真人)")
        print(f"  │     情感极性:       {row.get('sentiment_score',0.5):.2f}  ({'偏正面' if row.get('sentiment_score',0.5) > 0.6 else '偏负面' if row.get('sentiment_score',0.5) < 0.4 else '中性'})")
        print(f"  └{'─'*50}")

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
        
        if os.path.exists(out_path):
            try:
                old_df = pd.read_csv(out_path, encoding='utf-8-sig')
                final_df = pd.concat([old_df, result_df], ignore_index=True)
            except Exception:
                final_df = result_df
        else:
            final_df = result_df
            
        final_df.to_csv(out_path, index=False, encoding='utf-8-sig')

        tier_names = ['确定真人(0)', '大概率真人(1)', '不确定(2)', '比较可疑(3)', '确定水军(4)']
        print(f"\n{'='*60}")
        print(f"  本次标注！共 {len(labeled_rows)} 条")
        for t in range(5):
            cnt = sum(1 for r in labeled_rows if r['suspicion_label'] == t)
            if cnt > 0:
                print(f"  本次 {tier_names[t]}: {cnt} 条")
        print(f"  总库体积达到: {len(final_df)} 条，保存至: {out_path}")

        if len(final_df) >= 10:
            print(f"\n  正在训练 RandomForest 回归模型 (预测连续可疑度)...")
            from scoring import FEATURE_COLS
            feature_cols = FEATURE_COLS
            
            for c in feature_cols:
                if c not in final_df.columns:
                    final_df[c] = 0.0

            X = final_df[feature_cols].fillna(0)
            y = final_df['suspicion_score'] 

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
