import pandas as pd
import os
import sys

# 强制兼容 Windows 控制台输出 utf-8
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# 从我们重构的清洗管道中导入算好新特征的方法
from bot_pipeline import run_pipeline

def start_labeling(topic="中东局势彻底失控", sample_size=10):
    print("="*60)
    print("【专家级】微博水军人工鉴别实验室".center(55))
    print("="*60)
    print("正在拉取全新混合特征计算数据，请稍候约 5 - 15 秒...")
    
    try:
        # 使用管道进行完整内存抽取和特征挂载
        df = run_pipeline(topic, limit=sample_size)
    except Exception as e:
        print(f"数据管线抽取失败：{e}")
        return
        
    df_sample = df.copy()
    labeled_data = []
    
    print(f"📦 成功装载 {len(df_sample)} 条带高阶特征待鉴定数据，实验开始（输入 q 退出）...\n")
    
    for idx, row in df_sample.iterrows():
        print("-" * 50)
        print(f"调查样本 [{len(labeled_data) + 1}/{len(df_sample)}]")
        print(f"嫌疑人昵称：{row.get('用户昵称', row.get('ûǳ','未知'))}")
        print(f"社交生态：关注数({row.get('friends_count',0)}) | 粉丝数({row.get('followers_count',0)}) | 总发帖({row.get('statuses_count',0)})")
        print(f"账号简介：{row.get('description', '无')}")
        print(f"发帖设备：{row.get('发布工具', row.get('source', '未知'))}")
        
        text = str(row.get('微博正文', row.get('',''))).replace('\\n', '')
        if len(text) > 80: text = text[:80] + "..."
        print(f"本次暴言：\"{text}\"")
        print("-" * 50)
        
        while True:
            choice = input(f"您的判决 (【1】=水军/引流号  【0】=正常人类  【q】=保存并退出)：").strip()
            if choice in ['0', '1']:
                row_dict = row.to_dict()
                row_dict['Ground_Truth_Bot'] = int(choice)
                labeled_data.append(row_dict)
                print("✅ 记录已写入硬盘。\n")
                break
            elif choice.lower() == 'q':
                break
            else:
                print("⚠️ 输入无效，请键入 0, 1 或 q。")
                
        if choice.lower() == 'q':
            break

    if labeled_data:
        res_df = pd.DataFrame(labeled_data)
        out_path = "golden_testset_labeled.csv"
        res_df.to_csv(out_path, index=False, encoding='utf-8-sig')
        print("="*60)
        print(f"🎉 打标实验结束！本批次共凝聚了您 {len(res_df)} 条无比珍贵的心血结晶。")
        print(f"💽 数据已安全落盘至：{out_path}")
        print("下一步，你可以把这些金灿灿的样本喂给 Jupyter 里你的新模型了！")

if __name__ == "__main__":
    start_labeling()
