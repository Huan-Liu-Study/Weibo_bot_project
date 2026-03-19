# -*- coding: utf-8 -*-
"""Quick test for v1.7.0 incremental crawl system."""
import time
import topic_db
import bot_pipeline

print("[TEST] v1.7.0 Incremental Crawl Test")
print("=" * 50)

# --- Round 1: first crawl ---
print("\n[Round 1] First crawl (limit=15)...")
start = time.time()
df, info = bot_pipeline.run_pipeline("AI", limit=15)
elapsed = time.time() - start

print(f"  Time: {elapsed:.1f}s")
print(f"  new_fetched  = {info['new_fetched']}")
print(f"  total_fetched= {info['total_fetched']}")
print(f"  DataFrame rows: {len(df)}")

meta = topic_db.get_topic_meta("AI")
print(f"  DB meta: {meta}")

# --- Round 2: second crawl (continuation) ---
print("\n[Round 2] Second crawl / continuation (limit=15)...")
start2 = time.time()
df2, info2 = bot_pipeline.run_pipeline("AI", limit=15, continue_mode=True)
elapsed2 = time.time() - start2

print(f"  Time: {elapsed2:.1f}s")
print(f"  new_fetched  = {info2['new_fetched']}")
print(f"  total_fetched= {info2['total_fetched']}")
print(f"  DataFrame rows: {len(df2)}")

meta2 = topic_db.get_topic_meta("AI")
print(f"  DB meta: {meta2}")

# --- Assertions ---
print("\n" + "=" * 50)
if info2['total_fetched'] >= info['total_fetched']:
    print("[PASS] total_fetched is non-decreasing across rounds")
else:
    print("[FAIL] total_fetched decreased!")

if len(df2) >= len(df):
    print(f"[PASS] Aggregated DF grew or stayed same ({len(df)} -> {len(df2)})")
else:
    print(f"[WARN] Aggregated DF shrank ({len(df)} -> {len(df2)})")

print("\n[TEST] Done!")
