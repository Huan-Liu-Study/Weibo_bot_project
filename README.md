# 🛡️ 微博水军检测系统 (Weibo Bot Detection System)

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Machine Learning](https://img.shields.io/badge/ML-Random%20Forest-orange.svg)](https://scikit-learn.org/)

本系统是一款基于**机器学习**与**规则引擎**双驱动的微博社交机器人（水军）自动化检测工具。通过分析用户画像、发帖行为、语义特征等多维度数据，精准识别自动化脚本账号。

---

## ✨ 核心特性

- **9维核心特征体系**：包含日均发帖率、发帖间隔方差、互动量、语义拟人度等核心指标。
- **语义拟人度分析**：利用词汇丰富度、主观词密度、复句复杂度综合评估文本的“人类真实度”。
- **双引擎决策逻辑**：
  - **模型引擎**：RandomForestRegressor 提供 0-1 的细粒度可疑度评分。
  - **规则引擎**：内置“红旗否决”机制，对极端异常行为（如定时发帖、超量发帖）进行一票否决。
- **半自动标注工具**：集成了主动学习思想，支持人工复核与机器自动补齐。

---

## 📊 9 维模型特征展示

| 特征名 | 含义 | 说明 |
| :--- | :--- | :--- |
| `daily_post_rate` | 发帖频率 | 近期日均发帖率（log1p缩放） |
| `human_likeness_score` | 语义拟人度 | 词汇丰富度+主观词密度+复句复杂度 |
| `exclamation_density` | 感叹号密度 | 文本中感叹号占比 |
| `is_random_name` | 乱码昵称 | 是否5位以上数字昵称 |
| `engagement_count` | 互动量 | 近20条原创帖平均互动量 |
| `is_verified` | V认证 | 是否通过微博认证 |
| `sentiment_score` | 情感极性 | SnowNLP 情感分析得分 |
| `topic_diversity` | 话题多样性 | 识别固定刷榜行为 |
| `post_interval_variance` | 间隔方差 | 识别定时机器人的核心指标（log1p缩放） |

---

## 🛠️ 技术栈

- **语言**：Python 3.x
- **爬虫**：基于 Weibo-Search 的异步接口抓取
- **算法**：Scikit-learn (Random Forest), SnowNLP (情感分析)
- **数据**：Pandas, Numpy

---

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install pandas scikit-learn snownlp aiohttp joblib
```

### 2. 配置 Cookie
在 `weibo-search/weibo/settings.py` 中填入你的微博有效 Cookie（GitHub 仓库已通过 .gitignore 排除敏感信息）。

### 3. 运行检测
- **单账号检测**：运行 `detect_user.py`。
- **重训练模型**：运行 `rebuild_features_and_retrain.py`（基于金库数据重构特征并训练）。
- **人工标注**：使用 `semi_auto_label.py` 进行数据标注。

---

## 📂 文件结构说明

- `bot_pipeline.py`: 在线检测核心流水线
- `label_existing_data.py`: 特征计算与离线标注核心库
- `golden_testset_labeled.csv`: **项目金库**（包含384条高权重人工标注数据）
- `weibo_bot_rf_model.pkl`: 训练完成的预测模型

---

## ⚖️ 声明
本项仅供学术研究与毕设参考，使用爬虫时请遵守微博平台相关政策。
