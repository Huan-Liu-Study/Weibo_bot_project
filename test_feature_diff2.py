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
    
    print("\n=== Topic Detection Pipeline Features (from DB) ===")
    print(f"model_confidence: {data_dict.get('model_confidence')}")
    print(f"rule_suspicion: {data_dict.get('rule_suspicion')}")
    print(f"suspicion_score (DB): {data_dict.get('suspicion_score')}")
    print(f"exclamation_density: {data_dict.get('exclamation_density')}")
    print(f"is_random_name: {data_dict.get('is_random_name')}")
    print(f"is_verified: {data_dict.get('is_verified')}")
    print(f"sentiment_score: {data_dict.get('sentiment_score')}")
    
    print("\n=== Single User Detection Pipeline Features (from server.py) ===")
    res = analyze_single_user(str(uid))
    if "error" not in res:
        feats = res['features']
        print(f"exclamation_density: {feats.get('exclamation_density')}")
        print(f"is_random_name: {feats.get('is_random_name')}")
        print(f"is_verified: {feats.get('is_verified')}")
        print(f"sentiment_score: {feats.get('sentiment_score')}")
        print(f"suspicion_score (Server): {res['suspicion_score']}")
    else:
        print(res['error'])
else:
    print("User not found in DB.")
