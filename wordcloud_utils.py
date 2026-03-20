import re
from collections import Counter
from snownlp import SnowNLP

STOPWORDS = set([
    '的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你',
    '会', '着', '没', '看', '好', '自己', '这', '让', '那', '点', '还', '个', '把', '多', '去', '被', '走', '对', '谁', '太', '再',
    '里', '后', '想', '打', '起来', '过', '得', '能', '下', '等', '把', '我们', '你们', '他们', '它们', '微博', '分享', '链接', '全文',
    '转发', '哈哈', '表情', '视频', '图片', '今天', '一个', '就是', '还是', '怎么', '感觉', '真的', '现在', '因为', '所以', '如果', '但是',
    '开始', '发现', '已经', '看到', '出来', '还有', '一下', '非常', '比较', '这种', '那个', '这里', '那里', '其实', '可能', '知道'
])

def generate_wordcloud_data(texts, top_n=50):
    """使用 SnowNLP 进行分词并统计词频"""
    words = []
    for text in texts:
        if not text or not isinstance(text, str):
            continue
        try:
            # 过滤掉非中文字符，保留关键词质量
            clean_text = re.sub(r'[^\u4e00-\u9fa5]', '', text)
            if len(clean_text) < 2:
                continue
            s = SnowNLP(clean_text)
            for w in s.words:
                if len(w) > 1 and w not in STOPWORDS:
                    words.append(w)
        except Exception:
            continue
            
    counts = Counter(words).most_common(top_n)
    return [{"name": k, "value": v} for k, v in counts]
