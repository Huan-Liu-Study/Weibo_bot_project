"""
auto_label_remaining.py
========================
全自动标注脚本：
1. 读取 unlabeled_pool.csv (大蓄水池)
2. 排除已经在 golden_testset_labeled.csv 中的用户
3. 调用 API 补全画像和时间线，计算 15 维特征
4. 使用最新模型预测 + 红旗否决机制 自动打标
5. 将结果并入 golden_testset_labeled.csv
"""

import sys
import os
import pandas as pd
import numpy as np
import asyncio
import joblib
import re
from datetime import datetime

# 设置项目路径
project_dir = r'd:\Folders\Desktop\软件毕设\Weibo_bot_project'
sys.path.insert(0, project_dir)
os.chdir(project_dir)

from label_existing_data import _fetch_all, compute_15_features, _load_cookie

def apply_red_flags(score, row):
    """专家规则红旗否决机制"""
    piv = float(row.get('post_interval_variance', -1))
    dpr = float(row.get('daily_post_rate', 0))
    td = float(row.get('topic_diversity', 0.5))
    
    # 🔴 红旗1: 发帖间隔方差 <= 1 (且有数据)
    if 0 < piv <= 1:
        score = max(score, 0.55)
    
    # 🔴 红旗2: 日均发帖 >= 50
    if dpr >= 50:
        score = max(score, 0.55)
        
    # 🔴 红旗3: 话题多样性 <= 10% (非默认值)
    if td <= 0.1 and td != 0.5:
        score = max(score, 0.55)
        
    return score

async def main():
    print("=" * 60)
    print("  🚀 微博自动化标注流水线 (Auto-Labeling Pipeline)")
    print("=" * 60)

    # 1. 检查准备工作
    pool_file = 'unlabeled_pool.csv'
    golden_file = 'golden_testset_labeled.csv'
    model_file = 'weibo_bot_rf_model.pkl'

    if not os.path.exists(pool_file):
        print(f"❌ 找不到原始数据池 {pool_file}")
        return
    if not os.path.exists(model_file):
        print(f"❌ 找不到训练好的模型 {model_file}")
        return

    # 2. 读取数据并去重
    df_pool = pd.read_csv(pool_file, encoding='utf-8-sig')
    labeled_uids = set()
    if os.path.exists(golden_file):
        df_golden = pd.read_csv(golden_file, encoding='utf-8-sig')
        if 'user_id' in df_golden.columns:
            labeled_uids = set(df_golden['user_id'].unique())
    
    # 排除已标注用户
    df_remaining = df_pool[~df_pool['user_id'].isin(labeled_uids)].copy()
    unique_uids = df_remaining['user_id'].unique()
    
    if len(unique_uids) == 0:
        print("✅ 没有需要标注的新用户，所有用户均已在金库中。")
        return

    print(f"📦 发现 {len(unique_uids)} 个待标注新用户 (涉及 {len(df_remaining)} 条微博)")

    # 3. 补充完整 API 特征 (分批处理避免 API 被封)
    print(f"\n🌐 [1/4] 正在拉取用户画像与时间线数据 (使用最新 Cookie)...")
    cookie = _load_cookie()
    HEADERS = {'cookie': cookie, 'User-Agent': 'Mozilla/5.0'}
    
    # 限制每批次查询数量，防止超时
    batch_size = 50
    all_results = []
    for i in range(0, len(unique_uids), batch_size):
        batch = unique_uids[i:i+batch_size]
        print(f"  正在处理第 {i//batch_size + 1} 批 ({len(batch)} 人)...")
        results = await _fetch_all(batch, HEADERS)
        all_results.extend(results)
        await asyncio.sleep(1)

    user_map = {r['uid']: r for r in all_results if r}
    
    # 将画像字段映射回 DataFrame
    fields = ['followers_count', 'friends_count', 'statuses_count', 'description', 
              'avatar_hd', 'recent_post_times', 'recent_engagements', 'recent_topics', 'verified_reason']
    for field in fields:
        df_remaining[field] = df_remaining['user_id'].apply(lambda x: user_map.get(x, {}).get(field, ''))

    # 4. 计算特征
    print("\n⚙️ [2/4] 计算 15 维语义特征...")
    df_remaining = compute_15_features(df_remaining)

    # 5. 模型预测
    print("\n🤖 [3/4] 加载模型进行全自动评分...")
    model = joblib.load(model_file)
    feature_cols = [
        'follower_friend_ratio', 'daily_post_rate', 'human_likeness_score',
        'exclamation_density', 'is_random_name', 'engagement_rate', 'is_verified',
        'sentiment_score', 'topic_diversity', 'post_interval_variance'
    ]
    X = df_remaining[feature_cols].fillna(0)
    base_scores = model.predict(X)
    df_remaining['suspicion_score'] = base_scores

    # 6. 红旗否决机制
    print("🚩 [4/4] 应用专家红旗否决逻辑...")
    df_remaining['suspicion_score'] = df_remaining.apply(lambda r: apply_red_flags(r['suspicion_score'], r), axis=1)
    
    # 映射回 0-4 离散标签供统计
    # (0 < 0.125, 1 < 0.375, 2 < 0.625, 3 < 0.875, 4 >= 0.875)
    def score_to_label(s):
        if s < 0.125: return 0
        if s < 0.375: return 1
        if s < 0.625: return 2
        if s < 0.875: return 3
        return 4
    df_remaining['suspicion_label'] = df_remaining['suspicion_score'].apply(score_to_label)

    # 7. 写入金标准库
    print(f"\n💾 正在将结果存入 {golden_file}...")
    # 只取唯一用户的第一条记录（或者是合并方式，这里简单起见保留所有微博记录以扩充训练集）
    if os.path.exists(golden_file):
        df_final = pd.concat([df_golden, df_remaining], ignore_index=True)
    else:
        df_final = df_remaining
    
    df_final.to_csv(golden_file, index=False, encoding='utf-8-sig')

    # 打印总结
    print("\n" + "=" * 60)
    print("  ✅ 自动化标注任务完成！")
    print("=" * 60)
    print(f"  新增用户数: {len(unique_uids)}")
    print(f"  新增微博记录: {len(df_remaining)}")
    print(f"  标签分布:")
    dist = df_remaining['suspicion_label'].value_counts().sort_index().to_dict()
    label_names = {0: "真人", 1: "大概率真人", 2: "不确定", 3: "可疑", 4: "水军"}
    for l, count in dist.items():
        print(f"    - {label_names[l]}: {count} 条")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
