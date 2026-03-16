import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib

# 读取处理好的数据
data_path = 'weibo-search/结果文件/中东局势彻底失控/machine_learning_ready.csv'
df = pd.read_csv(data_path)

# v3: 15 维最终特征集（与 bot_pipeline.py 完全对齐）
feature_cols = [
    'follower_friend_ratio', 'daily_post_rate', 'text_len',
    'exclamation_density', 'link_count', 'is_default_avatar',
    'is_random_name', 'engagement_rate', 'is_verified',
    'sentiment_score', 'post_hour', 'desc_len',
    'urank', 'topic_count', 'post_interval_variance'
]

X = df[feature_cols].fillna(0)
y = df['is_bot']

# 训练全量数据的终极模型
print(f"正在使用 {len(df)} 条数据 × {len(feature_cols)} 个特征 深度训练随机森林...")
rf_model = RandomForestClassifier(n_estimators=100, random_state=42)
rf_model.fit(X, y)

# 保存模型为实体文件
model_filename = 'weibo_bot_rf_model.pkl'
joblib.dump(rf_model, model_filename)

print(f"模型已保存至：{model_filename}")
print(f"特征列表：{feature_cols}")
