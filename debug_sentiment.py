import sqlite3
import json
import sys

def debug_account(target_uid):
    conn = sqlite3.connect('topic_cache.db')
    cur = conn.cursor()
    cur.execute("SELECT data_json FROM topic_posts")
    rows = cur.fetchall()
    
    found = False
    for r in rows:
        data = json.loads(r[0])
        uid = str(data.get('user_id'))
        if uid == target_uid:
            found = True
            print(f"--- Data for {target_uid} ---")
            print(f"Name: {data.get('用户昵称')}")
            print(f"Content (current): {data.get('微博正文')}")
            # The sentiment in DB was likely calculated via text_for_features (v1.8.5)
            # Let's see if we can find recent_texts in the JSON
            recent = data.get('recent_texts', [])
            print(f"Recent Texts: {recent}")
            
            if recent:
                agg_text = "".join(recent[:3])
                print(f"Aggregated Text: {agg_text}")
                try:
                    from snownlp import SnowNLP
                    import re
                    # Aggressive clean: remove brackets like [打call] and symbols
                    clean = re.sub(r"\[.*?\]", "", agg_text)
                    clean = re.sub(r"http\S+", "", clean)
                    clean = re.sub(r"[#｜\n]", " ", clean).strip()
                    print(f"Aggressively Cleaned: {clean}")
                    sample = clean[:100]
                    s = SnowNLP(sample)
                    print(f"Aggressive SnowNLP score: {s.sentiments}")
                except Exception as e:
                    print(f"SnowNLP error: {e}")

            
            # Re-check single post
            try:
                from snownlp import SnowNLP
                import re
                text = data.get('微博正文', '')
                clean = re.sub(r"http\S+", "", text).strip()
                s = SnowNLP(clean[:100])
                print(f"Single post SnowNLP score: {s.sentiments}")
            except: pass

            break
            
    if not found:
        print(f"Account {target_uid} not found in DB.")
        
    conn.close()

if __name__ == "__main__":
    # Ensure UTF-8 output
    sys.stdout.reconfigure(encoding='utf-8')
    debug_account('1780005591')
