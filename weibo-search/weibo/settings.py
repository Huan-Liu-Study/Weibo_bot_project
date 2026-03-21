# -*- coding: utf-8 -*-

BOT_NAME = 'weibo'
SPIDER_MODULES = ['weibo.spiders']
NEWSPIDER_MODULE = 'weibo.spiders'
COOKIES_ENABLED = False
TELNETCONSOLE_ENABLED = False
LOG_LEVEL = 'DEBUG'
# 访问完一个页面再访问下一个时需要等待的时间，默认为10秒
DOWNLOAD_DELAY = 1
DEFAULT_REQUEST_HEADERS = {
    'Accept':
    'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-US;q=0.7',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
    # ⚠️ 不要在这里填写真实 Cookie！用户通过前端页面注入自己的 Cookie。
    # 此处仅作为占位符 / 回退默认值。
    'cookie': '',
}
ITEM_PIPELINES = {
    'weibo.pipelines.DuplicatesPipeline': 300,
    'weibo.pipelines.CsvPipeline': 301,
}
# 要搜索的关键词列表
KEYWORD_LIST = ['默认关键词']
# 微博类型：0全部 1原创 2热门 3关注人 4认证用户 5媒体 6观点
WEIBO_TYPE = 0
# 筛选内容：0不筛选 1图片 2视频 3音乐 4短链接
CONTAIN_TYPE = 0
REGION = ['全部']
START_DATE = '2026-01-01'
END_DATE = '2026-12-31'
FURTHER_THRESHOLD = 46
LIMIT_RESULT = 20
IMAGES_STORE = './'
FILES_STORE = './'