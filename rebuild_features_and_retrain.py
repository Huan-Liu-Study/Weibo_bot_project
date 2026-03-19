"""
rebuild_features_and_retrain.py
================================
处理已标注的 golden_testset_labeled.csv，计算完整的 14 维特征，
并重新训练 RandomForest 模型。

步骤：
1. 读取已标注数据
2. 通过 API 补充缺失字段（description, urank）
3. 计算 14 维特征
4. 训练模型 + 评估
5. 保存新模型
"""

import sys
import io
# 强制 Windows 控制台使用 UTF-8 输出
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np
import re
import asyncio
import joblib
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.metrics import classification_report, confusion_matrix
import os

# 特征计算已迁移到 label_existing_data.py 的 compute_15_features 中
from label_existing_data import compute_15_features, _fetch_all


# ===================== 1. Cookie 读取 =====================

def _load_cookie_from_settings():
    settings_path = 'weibo-search/weibo/settings.py'
    with open(settings_path, 'r', encoding='utf-8') as f:
        content = f.read()
    match = re.search(r"'cookie'\s*:\s*'([^']+)'", content)
    return match.group(1) if match else ''


# ===================== 2. 主流程 =====================

def main():
    print("=" * 60)
    print("  🔬 15 维特征重建 & RandomForest 重训练")
    print("=" * 60)

    # 1. 加载现有的 CSV (使用 _backup 避免覆盖问题，如果没有再用原文件)
    csv_path = 'golden_testset_labeled.csv'
    if not os.path.exists(csv_path):
        print(f"❌ 找不到文件: {csv_path}")
        return

    print(f"\n📂 加载已标注数据: {csv_path}")
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    print(f"  共 {len(df)} 条样本")

    # 检查标签分布
    label_col = 'suspicion_score'
    if label_col not in df.columns:
        print(f"❌ 未找到标签列 '{label_col}'，请确认 CSV 已标注")
        return
    else:
        dist = df[label_col].value_counts().to_dict()
        print(f"  标签分布: {dist}")

    # 2. 从 API 补充完整特征 (包含时间线)
    print("\n🌐 从微博 API 补充缺失的画像与时间线字段...")
    cookie = _load_cookie_from_settings()
    HEADERS = {
        'cookie': cookie,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    unique_users = df['user_id'].unique()
    print(f"  需要查询 {len(unique_users)} 个独立用户...")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    user_results = loop.run_until_complete(_fetch_all(unique_users, HEADERS))
    loop.close()

    user_map = {r['uid']: r for r in user_results if r}
    
    # 填充 API 取回的所有字段
    df['description'] = df['user_id'].apply(lambda x: user_map.get(x, {}).get('description', ''))
    df['avatar_hd'] = df['user_id'].apply(lambda x: user_map.get(x, {}).get('avatar_hd', ''))
    
    # 将字典中的列表转换为pandas能存入或计算的列
    # 仅当 API 返回非空数据时才覆盖，防止空结果覆盖 CSV 中已有的好数据
    for field in ['recent_post_times', 'recent_engagements', 'recent_topics']:
        def _safe_merge(uid, field=field):
            api_val = user_map.get(uid, {}).get(field, [])
            if api_val:  # API 返回了有效数据
                return api_val
            # API 为空，保留 CSV 中的原始值
            return df.loc[df['user_id'] == uid, field].iloc[0] if field in df.columns else []
        df[field] = df['user_id'].apply(_safe_merge)

    success = sum(1 for r in user_results if r and (r.get('followers_count', 0) > 0 or len(r.get('recent_post_times', [])) > 0))
    print(f"  ✅ 成功获取 {success}/{len(unique_users)} 个用户画像和时间线")

    # 计算 15 维新特征
    print("\n⚙️ 计算完整的 15 维语义特征...")
    df = compute_15_features(df)

    # 使用新的 15 维特征和连续打分逻辑
    feature_cols = [
                'daily_post_rate', 'human_likeness_score',
                'exclamation_density', 'is_random_name', 'engagement_count', 'is_verified',
                'sentiment_score', 'topic_diversity', 'post_interval_variance'
            ]
            
    # 只取有真实标签也就是人工审核过的数据（离散5档分数: 0, 0.25, 0.5, 0.75, 1.0）
    # 排除机器自动标注的连续分数数据，确保模型仅从专家判断中学习
    human_scores = {0.0, 0.25, 0.5, 0.75, 1.0}
    train_df = df.dropna(subset=['suspicion_score'])
    train_df = train_df[train_df['suspicion_score'].isin(human_scores)]
    print(f"  筛选人工标注数据: {len(train_df)} 条 (排除机器标注)")

    if len(train_df) == 0:
        print("未发现含有 suspicion_score 标注的数据，无法训练。")
        return

    X = train_df[feature_cols].fillna(0)
    # 不再预测离散的 Label (Ground_Truth_Bot)，而是预测连续的分数 suspicion_score
    y = train_df['suspicion_score']

    print(f"\n📊 特征矩阵: {X.shape[0]} 样本 × {X.shape[1]} 特征")

    from sklearn.ensemble import RandomForestRegressor
    
    # 用全量数据训练最终模型
    print("\n🏋️ 训练用于半自动初筛的最终 RandomForestRegressor 模型...")
    # 启用 max_features='sqrt' 和 max_depth=8 强制模型在没有粉关比时，去学习语义特征，防止单一特征过拟合
    rf_final = RandomForestRegressor(n_estimators=150, max_features='sqrt', max_depth=8, random_state=42)
    rf_final.fit(X, y)

    # 特征重要性
    importances = pd.Series(rf_final.feature_importances_, index=feature_cols).sort_values(ascending=False)
    print("\n📈 特征重要性排名:")
    for feat, imp in importances.items():
        bar = '█' * int(imp * 50)
        print(f"  {feat:30s} {imp:.4f} {bar}")

    # 保存模型
    model_path = 'weibo_bot_rf_model.pkl'
    joblib.dump(rf_final, model_path)
    print(f"\n💾 新模型已保存: {model_path}")

    # 保存带完整特征的数据集（用于后续分析）
    output_path = 'golden_testset_15features.csv'
    train_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"📁 完整特征数据集已保存: {output_path}")

    print("\n" + "=" * 60)
    print("  ✅ 模型特征迁移与重训练完成！")
    print("=" * 60)


if __name__ == '__main__':
    main()
