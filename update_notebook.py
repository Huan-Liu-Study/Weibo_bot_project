import json

notebook_path = 'd:/Folders/Desktop/软件毕设/Weibo_bot_project/1_数据清洗与特征工程.ipynb'

with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

new_cells = [
  {
   'cell_type': 'markdown',
   'metadata': {},
   'source': [
    '## 2. 数据清洗 (Data Cleaning)\n',
    '\n',
    '刚爬回来的数据有很多杂质。我们需要：\n',
    '- **删掉重复的微博**（爬虫翻页时可能抓到重复的数据）\n',
    '- **填补空缺值**（有的博主没有填个人简介，缺失的数字特征统一填为0）\n'
   ]
  },
  {
   'cell_type': 'code',
   'execution_count': None,
   'metadata': {},
   'outputs': [],
   'source': [
    '# 1. 剔除重复的抓取（避免重复计算同一条帖子）\n',
    'if "id" in df.columns:\n',
    '    df.drop_duplicates(subset=["id"], inplace=True)\n',
    'print(f"去重后剩余独立的微博数：{len(df)}")\n',
    '\n',
    '# 2. 补全缺失文本\n',
    'if "个人简介" in df.columns:\n',
    '    df["个人简介"] = df["个人简介"].fillna("")\n',
    '\n',
    '# 3. 将表示量的列强制设为整数类型，把缺失设为0\n',
    'num_cols = ["粉丝数", "关注数", "发博数", "reposts_count", "comments_count", "attitudes_count"]\n',
    'for col in num_cols:\n',
    '    if col in df.columns:\n',
    '        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)\n',
    '        \n',
    'print("\\n非常好！最脏乱差的数据清理完毕，接下来我们要开始提取判断机器人的高级特征指标了！")\n'
   ]
  }
]

nb['cells'].extend(new_cells)

with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
print("Notebook cells appended successfully.")
