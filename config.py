# -*- coding: utf-8 -*-
"""
config.py — 项目统一配置管理
==============================
所有模块共用的配置、路径、Cookie 读取逻辑。
避免在多个文件中重复实现相同的功能。
"""

import re
import os

# ===================== 路径常量 =====================

SCRAPY_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), 'weibo-search', 'weibo', 'settings.py')
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'weibo_bot_rf_model.pkl')


# ===================== Cookie 管理 =====================

def load_cookie() -> str:
    """从 weibo-search/weibo/settings.py 中动态读取 Cookie，统一管理。
    
    Returns:
        str: Cookie 字符串，读取失败则返回空字符串。
    """
    try:
        with open(SCRAPY_SETTINGS_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(r"'cookie'\s*:\s*'([^']+)'", content)
        return match.group(1) if match else ''
    except FileNotFoundError:
        print(f"[WARNING] Cookie 配置文件未找到: {SCRAPY_SETTINGS_PATH}")
        return ''
