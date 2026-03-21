import re
from collections import Counter
from snownlp import SnowNLP

import os

# 加载外部全局停用词表 (哈工大、百度、川大、中文停用词集合，超2000个词)
global_stopwords = set()
stopwords_path = os.path.join(os.path.dirname(__file__), 'stopwords.txt')
if os.path.exists(stopwords_path):
    with open(stopwords_path, 'r', encoding='utf-8') as f:
        global_stopwords.update([line.strip() for line in f if line.strip()])

# 项目专属强制过滤停用词块
PROJECT_STOPWORDS = set([
    # 新闻通稿/书面语高频词屏障 (防止媒体词汇霸榜)
    '近日', '记者', '表示', '女士', '先生', '报道', '平台', '相关', '部门', '调查', '官方', '回应', 
    '介绍', '情况', '联系', '消费者', '晚报', '晨报', '日报', '工作人员', '展示', '显示',
    # 常用动词、副词、残缺碎词
    '这家', '一并', '每个', '还有', '一下', '非常', '比较', '这种', '那个', '这里', '那里', '在于',
    '不仅', '此外', '因此', '那么', '齐鲁', '壹点', '在月', '买盒', '每盒'
])

STOPWORDS = global_stopwords.union(PROJECT_STOPWORDS)

def generate_wordcloud_data(texts, top_n=50):
    """使用 SnowNLP 进行分词并统计词频"""
    words = []
    for text in texts:
        if not text or not isinstance(text, str):
            continue
        try:
            # 过滤掉话题标签 #xxx#、头条【xxx】、表情[xxx]等固有格式
            no_tags_text = re.sub(r'#.*?#', '', text)
            no_tags_text = re.sub(r'【.*?】', '', no_tags_text)
            no_tags_text = re.sub(r'\[.*?\]', '', no_tags_text)
            
            # 把非中文字符（包含数字和标点）替换为"空格"而不是"空字符串"，防止首尾字强行粘连成新词！
            clean_text = re.sub(r'[^\u4e00-\u9fa5]', ' ', no_tags_text)
            if len(clean_text.strip()) < 2:
                continue
            s = SnowNLP(clean_text)
            for w in s.words:
                if len(w) > 1 and w not in STOPWORDS:
                    words.append(w)
        except Exception:
            continue
            
    counts = Counter(words).most_common(top_n)
    return [{"name": k, "value": v} for k, v in counts]
