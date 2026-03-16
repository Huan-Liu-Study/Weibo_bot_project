import asyncio
import aiohttp
import sys
import re

def _load_cookie():
    with open('weibo-search/weibo/settings.py', 'r', encoding='utf-8') as f:
        content = f.read()
    match = re.search(r"'cookie'\s*:\s*'([^']+)'", content)
    return match.group(1) if match else ''

async def test_fetch_timeline():
    cookie = _load_cookie()
    uid = '1645578093'
    url = f'https://weibo.com/ajax/statuses/mymblog?uid={uid}&page=1&feature=0'
    headers = {
        'cookie': cookie, 
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': f'https://weibo.com/u/{uid}',
        'Accept': 'application/json, text/plain, */*'
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            print(f"Status: {resp.status}")
            if resp.status == 200:
                data = await resp.json()
                list_data = data.get('data', {}).get('list', [])
                print(f"Got {len(list_data)} recent posts")
                if list_data:
                    times = [item.get('created_at') for item in list_data]
                    print("Recent post times:", times)

asyncio.run(test_fetch_timeline())
