import asyncio
import aiohttp
import pandas as pd
from label_existing_data import _fetch_one, _load_cookie
from scoring import is_news_media, _MEDIA_KEYWORDS

async def debug_user(uid):
    cookie = _load_cookie()
    headers = {
        'cookie': cookie,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    async with aiohttp.ClientSession() as session:
        user_info = await _fetch_one(session, uid, headers)
        
        print(f"--- Debug Info for UID: {uid} ---")
        print(f"Screen Name: {user_info.get('screen_name')}")
        print(f"Verified Reason: {user_info.get('verified_reason')}")
        print(f"Description: {user_info.get('description')}")
        print(f"Current Keywords in scoring.py: {_MEDIA_KEYWORDS}")
        
        # Test is_news_media
        row = {
            'verified_reason': user_info.get('verified_reason', ''),
            'description': user_info.get('description', ''),
            'screen_name': user_info.get('screen_name', ''),
            '用户昵称': user_info.get('screen_name', '')
        }
        
        matched_reason = [kw for kw in _MEDIA_KEYWORDS if kw in str(row['verified_reason']).lower()]
        matched_desc = [kw for kw in _MEDIA_KEYWORDS if kw in str(row['description']).lower()]
        matched_name = [kw for kw in _MEDIA_KEYWORDS if kw in str(row['screen_name']).lower()]
        
        print(f"\nMatched in Reason: {matched_reason}")
        print(f"Matched in Description: {matched_desc}")
        print(f"Matched in Name (Old dimension): {matched_name}")
        
        is_media = is_news_media(row)
        print(f"\nResult of is_news_media(row): {is_media}")

if __name__ == "__main__":
    uid = "7020977254"
    asyncio.run(debug_user(uid))
