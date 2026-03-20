import sqlite3
import json
import asyncio
from server import analyze_single_user

conn = sqlite3.connect('topic_cache.db')
c = conn.cursor()
c.execute("SELECT id, data_json FROM topic_posts WHERE data_json LIKE '%趁着大好年华去走走%' LIMIT 1")
row = c.fetchone()
conn.close()

if row:
    print("\n=== Topic Detection Pipeline Features (from DB) ===")
    data = json.loads(row[1])
    print(f"human_likeness_score: {data.get('human_likeness_score')}")
    print(f"model_confidence: {data.get('model_confidence')}")
    
    uid = data.get('user_id')
    print("\n=== Single User Detection Pipeline Features (from server.py) ===")
    res = analyze_single_user(str(uid))
    if "error" not in res:
        feats = res['features']
        print(f"human_likeness_score: {feats.get('human_likeness_score')}")
        print(f"model_confidence: {res.get('suspicion_score')}") # Approximate mapped output
