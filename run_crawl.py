"""准备爬虫设置并运行一次爬虫来收集训练数据"""
import re
import subprocess
import sys
import os

settings_path = 'weibo-search/weibo/settings.py'
with open(settings_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r"KEYWORD_LIST = \[.*?\]", "KEYWORD_LIST = ['中东局势彻底失控']", content)
content = re.sub(r"LIMIT_RESULT = \d+", "LIMIT_RESULT = 50", content)
content = re.sub(r"DOWNLOAD_DELAY = \d+", "DOWNLOAD_DELAY = 2", content)

with open(settings_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Settings updated: topic=中东局势彻底失控, limit=50, delay=2")

# 清理旧数据
csv_path = 'weibo-search/结果文件/中东局势彻底失控/中东局势彻底失控.csv'
if os.path.exists(csv_path):
    os.remove(csv_path)
    print(f"Cleaned old file: {csv_path}")

# 运行爬虫
print("Starting Scrapy crawler...")
subprocess.run([sys.executable, "-m", "scrapy", "crawl", "search"], cwd="weibo-search", check=True)
print("Crawl complete!")

# 检查结果
import pandas as pd
if os.path.exists(csv_path):
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    print(f"Collected {len(df)} weibos from {df.iloc[:, 2].nunique()} unique users")
else:
    print("ERROR: No output file generated!")
