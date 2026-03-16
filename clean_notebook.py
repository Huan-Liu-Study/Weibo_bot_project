import json
import nbformat
from nbconvert.preprocessors import ExecutePreprocessor

file_path = "1_数据清洗与特征工程.ipynb"
print(f"Cleaning {file_path}...")
with open(file_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)
    
for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source = cell['source']
        
        # Remove existing bad lines
        source = [line for line in source if 'df.rename(' not in line]
        
        # Re-insert the specific line cleanly
        for i, line in enumerate(source):
            if "df = pd.read_csv(data_path)" in line:
                source.insert(i+1, "df.rename(columns={'ͷurl': '头像url', 'ûǳ': '用户昵称'}, inplace=True, errors='ignore')\n")
                source.insert(i+2, "import re\n")
                break # Only do it once
        
        cell['source'] = source
                
with open(file_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f"Executing {file_path}...")
with open(file_path, 'r', encoding='utf-8') as f:
    nb = nbformat.read(f, as_version=4)
    
ep = ExecutePreprocessor(timeout=600, kernel_name='python3')
ep.preprocess(nb, {'metadata': {'path': '.'}})

with open(file_path, 'w', encoding='utf-8') as f:
    nbformat.write(nb, f)

print("1 Done. Executing 2...")
file_path_2 = "2_机器学习与模型预测.ipynb"
with open(file_path_2, 'r', encoding='utf-8') as f:
    nb_2 = nbformat.read(f, as_version=4)

ep_2 = ExecutePreprocessor(timeout=600, kernel_name='python3')
ep_2.preprocess(nb_2, {'metadata': {'path': '.'}})

with open(file_path_2, 'w', encoding='utf-8') as f:
    nbformat.write(nb_2, f)

print("All Done.")
