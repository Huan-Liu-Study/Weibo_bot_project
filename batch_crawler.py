import subprocess
import sys
import os
import pandas as pd
import time
import re

TOPICS = [
    "杨紫染红发",             # 娱乐
    "西安不倒翁小姐姐宣布离职", # 社会
    "三大平台的养老剧"         # 商业
]

LIMIT = 200  # 每个话题抓取的数量 (为了最终凑成 500-1000 人)

def run_scrapy(topic):
    settings_path = 'weibo-search/weibo/settings.py'
    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("[ERROR] 找不到 settings.py，请在项目根目录运行")
        return False
        
    content = re.sub(r"KEYWORD_LIST = \[.*?\]", f"KEYWORD_LIST = ['{topic}']", content)
    content = re.sub(r"LIMIT_RESULT = \d+", f"LIMIT_RESULT = {LIMIT}", content)
    # 设置一个温和的抓取间隔，防止被封 IP
    content = re.sub(r"DOWNLOAD_DELAY = \d+", "DOWNLOAD_DELAY = 1", content)
    
    # 获取动态日期 (近7天)
    from datetime import datetime, timedelta
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    content = re.sub(r"START_DATE = '.*?'", f"START_DATE = '{start_date}'", content)
    content = re.sub(r"END_DATE = '.*?'", f"END_DATE = '{end_date}'", content)
    
    with open(settings_path, 'w', encoding='utf-8') as f:
        f.write(content)

    csv_path = f'weibo-search/结果文件/{topic}/{topic}.csv'
    if os.path.exists(csv_path):
        os.remove(csv_path)

    print(f"\n==============================================")
    print(f" 开始抓取话题: 【{topic}】 (目标: {LIMIT} 条)")
    print(f"==============================================")
    
    try:
        # Popen to not capture all output and hang, use subprocess.run with timeout
        result = subprocess.run([sys.executable, "-m", "scrapy", "crawl", "search"], cwd="weibo-search", capture_output=True)
        # Even if result.returncode != 0, if the CSV exists and has data, we should accept it
        # because Scrapy often hits 403 rate limits at the very end of crawling
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path, encoding='utf-8-sig')
                if len(df) > 0:
                    print(f" [OK] 抓取完成！共获得 {len(df)} 条数据。 (退出码: {result.returncode})")
                    return csv_path
                else:
                    print(" [ERROR] 生成的 CSV 为空。")
                    return None
            except Exception as e:
                print(f" [ERROR] 无法读取 CSV: {e}")
                return None
        else:
            print(f" [ERROR] Scrapy 未生成 CSV 文件。退出码: {result.returncode}")
            return None
    except Exception as e:
        print(f" [ERROR] 执行失败: {e}")
        return None

def main():
    merged_pool = []
    
    # 之前的老数据（中东局势），已经存在，我们不需要重新爬，只要合并就行了
    old_csv = 'weibo-search/结果文件/中东局势彻底失控/中东局势彻底失控.csv'
    if os.path.exists(old_csv):
        print(f"找到旧数据集: 中东局势彻底失控.csv")
        df_old = pd.read_csv(old_csv, encoding='utf-8-sig')
        df_old['topic_query'] = '中东局势彻底失控'
        merged_pool.append(df_old)
        
    for topic in TOPICS:
        path = run_scrapy(topic)
        if path:
            df = pd.read_csv(path, encoding='utf-8-sig')
            # 打上话题来源标签，方便后面做增量训练时区分
            df['topic_query'] = topic
            merged_pool.append(df)
            
        print("休息 5 秒，准备抓取下一个话题...")
        time.sleep(5)
        
    if merged_pool:
        # 合并所有数据
        final_df = pd.concat(merged_pool, ignore_index=True)
        # 去重（基于微博ID）
        if 'id' in final_df.columns:
            final_df = final_df.drop_duplicates(subset=['id'])
            
        out_path = 'unlabeled_pool.csv'
        final_df.to_csv(out_path, index=False, encoding='utf-8-sig')
        print(f"\n==============================================")
        print(f" 批量抓取结束！")
        print(f" 所有话题混合池保存至: {out_path}")
        print(f" 混合池总行数 (未去重前): {len(final_df)}")
        print(f" 包含独立用户数: {final_df['user_id'].nunique()}")
        print(f"==============================================")
    else:
        print("\n[ERROR] 没有任何数据抓取成功。")

if __name__ == "__main__":
    main()
