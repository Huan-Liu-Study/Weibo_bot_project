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
    print(f"user_id: {data_dict.get('user_id')}")
    print(f"model_confidence: {data_dict.get('model_confidence')}")
    print(f"rule_suspicion: {data_dict.get('rule_suspicion')}")
    print(f"suspicion_score (DB): {data_dict.get('suspicion_score')}")
    print(f"exclamation_density: {data_dict.get('exclamation_density')}")
    print(f"is_random_name: {data_dict.get('is_random_name')}")
    print(f"is_verified: {data_dict.get('is_verified')}")
    print(f"sentiment_score: {data_dict.get('sentiment_score')}")
    print(f"post_interval_variance: {data_dict.get('post_interval_variance')}")
    print(f"daily_post_rate: {data_dict.get('daily_post_rate')}")
    print(f"engagement_count: {data_dict.get('engagement_count')}")
    print(f"topic_diversity: {data_dict.get('topic_diversity')}")
else:
    print("User not found.")
