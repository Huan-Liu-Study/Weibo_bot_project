import sqlite3
import json

conn = sqlite3.connect('topic_cache.db')
c = conn.cursor()
c.execute("SELECT id, data_json FROM topic_posts WHERE data_json LIKE '%趁着大好年华去走走%' LIMIT 1")
row = c.fetchone()
conn.close()

if row:
    data_dict = json.loads(row[1])
    print("\n=== Topic Detection Pipeline Features (from DB) ===")
    print(f"human_likeness_score: {data_dict.get('human_likeness_score')}")
    print(f"engagement_count: {data_dict.get('engagement_count')}")
else:
    print("User not found.")
