import asyncio
import pandas as pd
from server import analyze_single_user

# The UID of "趁着大好年华去走走"
# Let's search by name in SQLite
import sqlite3
conn = sqlite3.connect('topic_cache.db')
c = conn.cursor()
c.execute("SELECT id, data_json FROM topic_posts WHERE data_json LIKE '%趁着大好年华去走走%' LIMIT 1")
row = c.fetchone()
conn.close()

if row:
    import json
    data_dict = json.loads(row[1])
    uid = data_dict.get('user_id')
    print(f"Found UID: {uid}")
    
    print("\n=== Topic Detection Pipeline Features (from DB) ===")
    print(f"post_interval_variance: {data_dict.get('post_interval_variance')}")
    print(f"daily_post_rate: {data_dict.get('daily_post_rate')}")
    print(f"engagement_count: {data_dict.get('engagement_count')}")
    print(f"topic_diversity: {data_dict.get('topic_diversity')}")
    print(f"suspicion_score (in DB): {data_dict.get('suspicion_score')}")
    
    print("\n=== Single User Detection Pipeline Features (from server.py) ===")
    res = analyze_single_user(str(uid))
    if "error" not in res:
        feats = res['features']
        print(f"post_interval_variance: {feats.get('post_interval_variance')}")
        print(f"daily_post_rate: {feats.get('daily_post_rate')}")
        print(f"engagement_count: {feats.get('engagement_count')}")
        print(f"topic_diversity: {feats.get('topic_diversity')}")
        print(f"suspicion_score (in Server): {res['suspicion_score']}")
    else:
        print(res['error'])
else:
    print("User not found in DB.")
