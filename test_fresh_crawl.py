import asyncio
from bot_pipeline import run_pipeline
from server import analyze_single_user
import topic_db

topic = "中美博弈"
# Clear DB to force a completely fresh fetch and feature computation
topic_db.clear_topic(topic)

df, meta = run_pipeline(topic, limit=10)

if len(df) > 0:
    bot_df = df[df['is_bot_pred'] == 1]
    if len(bot_df) == 0:
        row = df.iloc[0]
    else:
        row = bot_df.iloc[0]
        
    uid = row['user_id']
    topic_conf = row['model_confidence']
    topic_score = row['suspicion_score']
    
    print(f"\n=== FRESH Topic Pipeline ===")
    print(f"UID: {uid}")
    print(f"Topic model_confidence: {topic_conf}")
    print(f"Topic suspicion_score: {topic_score}")
    
    print("\n=== FRESH Single User Pipeline ===")
    res = analyze_single_user(str(uid))
    if 'error' not in res:
        print(f"Single User suspicion_score: {res['suspicion_score']}")
    else:
        print(res['error'])
else:
    print("No posts found.")
