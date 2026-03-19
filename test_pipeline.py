import traceback
from bot_pipeline import run_pipeline
try:
    df = run_pipeline('test', 5)
    print("SUCCESS! Shape:", df.shape)
    print("Columns:", list(df.columns))
except Exception as e:
    traceback.print_exc()
