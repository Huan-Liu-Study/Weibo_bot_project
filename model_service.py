# -*- coding: utf-8 -*-
"""
model_service.py — 模型管理服务层 (v3.0)
==========================================
为 Web 前端提供模型信息查询和一键重训练功能。
"""

import os
import json
import joblib
import numpy as np
import pandas as pd
from datetime import datetime

from scoring import FEATURE_COLS
from features import compute_model_features

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'weibo_bot_rf_model.pkl')
GOLDEN_CSV = os.path.join(os.path.dirname(__file__), 'golden_testset_labeled.csv')

# ===================== 模型信息 =====================

def get_model_info():
    """
    读取当前 pkl 模型的元信息和特征权重。
    返回：模型类型、训练样本数估算、最后修改时间、特征权重排名。
    """
    result = {
        'model_exists': False,
        'model_type': '',
        'last_modified': '',
        'feature_importances': {},
        'feature_cols': FEATURE_COLS,
        'training_samples': 0,
        'golden_csv_exists': False,
        'label_distribution': {},
        'new_labels_count': 0
    }

    # 0. 新增标注count
    try:
        import sqlite3
        label_db = os.path.join(os.path.dirname(__file__), 'label_store.db')
        if os.path.exists(label_db):
            lconn = sqlite3.connect(label_db)
            cnt = lconn.execute("SELECT COUNT(*) FROM labeled_users WHERE trained = 0").fetchone()[0]
            lconn.close()
            result['new_labels_count'] = cnt
    except Exception:
        pass

    # 1. 模型文件信息
    if os.path.exists(MODEL_PATH):
        result['model_exists'] = True
        mtime = os.path.getmtime(MODEL_PATH)
        result['last_modified'] = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')

        try:
            model = joblib.load(MODEL_PATH)
            result['model_type'] = type(model).__name__

            if hasattr(model, 'feature_importances_'):
                importances = model.feature_importances_
                result['feature_importances'] = {
                    FEATURE_COLS[i]: round(float(importances[i]), 4)
                    for i in range(min(len(FEATURE_COLS), len(importances)))
                }

            if hasattr(model, 'n_estimators'):
                result['n_estimators'] = model.n_estimators
            if hasattr(model, 'max_depth'):
                result['max_depth'] = model.max_depth

        except Exception as e:
            result['error'] = str(e)

    # 2. 训练数据信息
    if os.path.exists(GOLDEN_CSV):
        result['golden_csv_exists'] = True
        try:
            df = pd.read_csv(GOLDEN_CSV, encoding='utf-8-sig')
            result['training_samples'] = len(df)

            if 'suspicion_label' in df.columns:
                dist = df['suspicion_label'].value_counts().to_dict()
                label_names = {0: '确定真人', 1: '大概率真人', 2: '不确定', 3: '比较可疑', 4: '几乎确定水军'}
                result['label_distribution'] = {
                    label_names.get(int(k), str(k)): int(v) for k, v in dist.items()
                }
            elif 'suspicion_score' in df.columns:
                # 从连续分数反推离散标签
                def score_to_label(s):
                    if s < 0.125: return 0
                    if s < 0.375: return 1
                    if s < 0.625: return 2
                    if s < 0.875: return 3
                    return 4
                labels = df['suspicion_score'].apply(score_to_label)
                dist = labels.value_counts().to_dict()
                label_names = {0: '确定真人', 1: '大概率真人', 2: '不确定', 3: '比较可疑', 4: '几乎确定水军'}
                result['label_distribution'] = {
                    label_names.get(int(k), str(k)): int(v) for k, v in dist.items()
                }
        except Exception as e:
            result['csv_error'] = str(e)

    return result


# ===================== 模型重训练 =====================

def retrain_model():
    """
    从 golden_testset_labeled.csv 重新训练 RandomForest 模型。
    返回训练结果摘要。
    """
    if not os.path.exists(GOLDEN_CSV):
        return {'status': 'error', 'message': '未找到训练数据文件 golden_testset_labeled.csv'}

    try:
        df = pd.read_csv(GOLDEN_CSV, encoding='utf-8-sig')
    except Exception as e:
        return {'status': 'error', 'message': f'读取 CSV 失败: {str(e)}'}

    if len(df) < 10:
        return {'status': 'error', 'message': f'训练样本不足（当前 {len(df)} 条，最少需要 10 条）'}

    # 确保特征列存在
    for c in FEATURE_COLS:
        if c not in df.columns:
            df[c] = 0.0

    X = df[FEATURE_COLS].fillna(0)

    # 确定标签列
    if 'suspicion_score' in df.columns:
        y = df['suspicion_score'].fillna(0.5)
    else:
        return {'status': 'error', 'message': '未找到 suspicion_score 标签列'}

    # 训练回归模型
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import cross_val_score, KFold

    rf = RandomForestRegressor(n_estimators=200, max_features='sqrt', max_depth=8, random_state=42)

    # 交叉验证
    n_splits = min(5, len(df))
    if n_splits >= 2:
        cv = KFold(n_splits=n_splits, shuffle=True, random_state=42)
        mae_scores = cross_val_score(rf, X, y, cv=cv, scoring='neg_mean_absolute_error')
        r2_scores = cross_val_score(rf, X, y, cv=cv, scoring='r2')
        cv_mae = round(float(-mae_scores.mean()), 4)
        cv_r2 = round(float(r2_scores.mean()), 4)
    else:
        cv_mae = None
        cv_r2 = None

    # 全量训练
    rf.fit(X, y)

    # 特征权重
    importances = {
        FEATURE_COLS[i]: round(float(rf.feature_importances_[i]), 4)
        for i in range(len(FEATURE_COLS))
    }

    # 保存模型
    joblib.dump(rf, MODEL_PATH)

    return {
        'status': 'success',
        'message': '模型重训练完成！',
        'training_samples': len(df),
        'cv_mae': cv_mae,
        'cv_r2': cv_r2,
        'feature_importances': importances,
        'model_type': 'RandomForestRegressor',
        'trained_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
