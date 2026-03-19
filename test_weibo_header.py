import requests
import re
from urllib.parse import quote

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
    'cookie': 'SUB=_2AkMUW7A8f8NxqwJRmPEUym7nbo5_zg_EieKl26cIJRNw1Q8JtQJ5uM450TigS9l2N3B3l3x1P_1uP_;'  # Dummy cookie just in case
}

topic_encoded = quote("#小米发布会#")
url = f"https://s.weibo.com/weibo?q={topic_encoded}"
r = requests.get(url, headers=headers)

text = r.text
print(f"Length: {len(text)}")

# Look for patterns like "阅读X亿 讨论Y万"
matches = re.findall(r'<p\s+class="s-item">([^<]+)</p>', text)
print("P tags:", matches)

matches2 = re.findall(r'阅读(.*?)讨论(.*?)<', text.replace('\n', '').replace(' ', ''))
print("Reading/Discussion pattern:", matches2)

# It's usually inside <div class="card-title"> or similar.
# Let's search string literals
idx = text.find('阅读')
if idx != -1:
    print(text[idx-50:idx+150])

