import traceback
from bot_pipeline import run_pipeline
from server import build_topic_response
import json

try:
    print("Running pipeline...")
    df = run_pipeline('test', 5)
    print("Pipeline success. Building response...")
    resp = build_topic_response(df)
    print("Response built successfully. Keys:", resp.keys())
    print("Testing JSON serialization...")
    json_str = json.dumps(resp)
    print("JSON serialization successful. Length:", len(json_str))
except Exception as e:
    print("ERROR CAUGHT:")
    traceback.print_exc()
