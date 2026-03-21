import asyncio
import aiohttp
import re
from logger import logger

async def fetch_user_profile_and_timeline(session, uid, headers):
    """
    异步获取单个用户的画像数据（粉丝、简介等）及其最近动态（用于计算时序特征和语义特征）。
    整合自原 label_existing_data.py 和 bot_pipeline.py，具备更高的容错性。
    """
    # 1. 获取基本画像
    # 账号 ID 如果全是数字，应使用 uid 参数；如果是自定义字符串名，用 custom 参数
    is_numeric = str(uid).isdigit()
    param = f"uid={uid}" if is_numeric else f"custom={uid}"
    url_info = f'https://weibo.com/ajax/profile/info?{param}'
    
    h = headers.copy()
    h['Referer'] = f'https://weibo.com/u/{uid}'
    h['Accept'] = 'application/json, text/plain, */*'
    
    result = {
        'uid': uid, 
        'screen_name': '', 
        'followers_count': 0, 
        'friends_count': 0,
        'statuses_count': 0, 
        'created_at': '', 
        'description': '',
        'avatar_hd': '', 
        'recent_post_times': [],
        'recent_engagements': [], 
        'recent_topics': [], 
        'verified_reason': '',
        'recent_texts': []
    }
    
    try:
        await asyncio.sleep(0.15)
        async with session.get(url_info, headers=h, timeout=8) as resp:
            if resp.status == 200:
                data = await resp.json()
                u = data.get('data', {}).get('user', {})
                if u:
                    for k in result:
                        if k not in ['uid', 'recent_post_times', 'recent_texts', 'recent_engagements', 'recent_topics', 'user_authentication']:
                            result[k] = u.get(k, result[k])
                    
                    # Ensure Random Forest 'is_verified' feature triggers identically to Scrapy data
                    if u.get('verified') == True:
                        result['user_authentication'] = "微博认证"
                    else:
                        result['user_authentication'] = ""
    except Exception as e:
        logger.warning(f"  [!] fetch profile failed {uid}: {e}")

    # 2. 获取近期发帖列表 (用于时序特征与互动特征)
    url_timeline = f'https://weibo.com/ajax/statuses/mymblog?uid={uid}&page=1&feature=0'
    try:
        await asyncio.sleep(0.15)
        async with session.get(url_timeline, headers=h, timeout=8) as resp:
            if resp.status == 200:
                data = await resp.json()
                posts = data.get('data', {}).get('list', [])
                if posts:
                    result['recent_post_times'] = [p.get('created_at') for p in posts if p.get('created_at')]
                    
                    # 必须是该用户自己发的原创帖，不能是单纯的转发，也不能是点赞别人的帖子
                    eng_list = []
                    topics_list = []
                    text_list = []
                    uid_str = str(uid)
                    
                    for p in posts:
                        is_own_post = str(p.get('user', {}).get('id', '')) == uid_str
                        is_retweet = 'retweeted_status' in p
                        text = p.get('text_raw', p.get('text', ''))
                        
                        is_valid_post = False
                        if is_own_post:
                            if not is_retweet:
                                is_valid_post = True
                            else:
                                # 检查是否为带有 5 个字以上自定义评论的转发
                                custom_comment = text.split('//')[0]
                                custom_comment = re.sub(r'转发微博|Repost|回复@\S+:', '', custom_comment).strip()
                                if len(custom_comment) > 5:
                                    is_valid_post = True
                                    
                        if is_valid_post:
                            eng = p.get('reposts_count', 0) + p.get('comments_count', 0) + p.get('attitudes_count', 0)
                            eng_list.append(eng)
                            
                            # 提取特征：话题多样性
                            found_topics = re.findall(r'#([^#]+)#', text)
                            if found_topics:
                                topics_list.extend(found_topics)
                            
                            text_list.append(text)
                    
                    result['recent_engagements'] = eng_list
                    result['recent_topics'] = topics_list
                    result['recent_texts'] = text_list
    except Exception as e:
        logger.warning(f"  [!] fetch timeline failed {uid}: {e}")

    return result

async def fetch_all_users_info(uids, headers):
    """并发获取所有用户画像及动态列表"""
    async with aiohttp.ClientSession() as s:
        tasks = [fetch_user_profile_and_timeline(s, uid, headers) for uid in uids]
        return await asyncio.gather(*tasks)
