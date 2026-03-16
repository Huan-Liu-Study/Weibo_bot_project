import json
import nbformat
from nbconvert.preprocessors import ExecutePreprocessor

file_path = "2_机器学习与模型预测.ipynb"
print(f"Fixing missing values in {file_path}...")
with open(file_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source = cell['source']
        for i, line in enumerate(source):
            if "X = df[feature_cols]" in line:
                source[i] = "X = df[feature_cols].fillna(0)\n"

with open(file_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print("Executing 2_机器学习与模型预测.ipynb...")
with open(file_path, 'r', encoding='utf-8') as f:
    nb_2 = nbformat.read(f, as_version=4)

ep_2 = ExecutePreprocessor(timeout=600, kernel_name='python3')
ep_2.preprocess(nb_2, {'metadata': {'path': '.'}})

with open(file_path, 'w', encoding='utf-8') as f:
    nbformat.write(nb_2, f)
print("Done!")
