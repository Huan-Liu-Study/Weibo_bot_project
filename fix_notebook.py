import json
import nbformat
from nbconvert.preprocessors import ExecutePreprocessor

def fix_and_run(file_path):
    print(f"Fixing {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        nb = json.load(f)
        
    for cell in nb['cells']:
        if cell['cell_type'] == 'code':
            source = cell['source']
            for i, line in enumerate(source):
                if "df = pd.read_csv(data_path)" in line:
                    source.insert(i+1, "df.rename(columns={'ͷurl': '头像url', 'ûǳ': '用户昵称', 'ͷurl': '头像url'}, inplace=True, errors='ignore')\n")
                if "df['description'] = df['description'].fillna('')" in line or "df['description'] = df.get('description'" in line:
                    source[i] = "df['description'] = df.get('description', pd.Series(['']*len(df))).fillna('')\n"
                    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)

    print(f"Executing {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        nb = nbformat.read(f, as_version=4)
        
    ep = ExecutePreprocessor(timeout=600, kernel_name='python3')
    ep.preprocess(nb, {'metadata': {'path': '.'}})
    
    with open(file_path, 'w', encoding='utf-8') as f:
        nbformat.write(nb, f)

fix_and_run("1_数据清洗与特征工程.ipynb")
print("1 Done. Now 2...")
fix_and_run("2_机器学习与模型预测.ipynb")
print("All Done.")
