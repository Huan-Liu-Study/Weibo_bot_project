from flask import Flask, render_template, request, jsonify
from bot_pipeline import run_pipeline
import traceback
import json
import numpy as np
import pandas as pd

app = Flask(__name__)

# Helper function to convert Pandas/Numpy types to native Python types for JSON serialization
def clean_for_json(df):
    """Convert dataframe to JSON-safe list of dicts, replacing all NaN/NaT with None"""
    import math
    records = df.to_dict('records')
    for record in records:
        for k, v in list(record.items()):
            if v is None:
                continue
            elif isinstance(v, float) and math.isnan(v):
                record[k] = None
            elif isinstance(v, (np.int64, np.int32)):
                record[k] = int(v)
            elif isinstance(v, (np.float64, np.float32)):
                if np.isnan(v) or np.isinf(v):
                    record[k] = None
                else:
                    record[k] = float(v)
            elif isinstance(v, np.bool_):
                record[k] = bool(v)
            elif hasattr(v, 'isoformat'):  # datetime/Timestamp
                record[k] = str(v)
            elif pd.isna(v):
                record[k] = None
    return records

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/detect', methods=['POST'])
def detect_bots():
    data = request.json
    topic = data.get('topic', '')
    limit = int(data.get('limit', 15))
    
    if not topic:
        return jsonify({"error": "请输入有效的微博话题或关键词"}), 400
        
    try:
        # Calls the scraper and ML prediction pipeline end-to-end
        df = run_pipeline(topic, limit)
        return jsonify(build_response(df))
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"流水线执行失败: {str(e)}"}), 500

def build_response(df):
    """Build the standard JSON response from any DataFrame"""
    total_scanned = len(df)
    bot_count = int(df['is_bot_pred'].sum()) if 'is_bot_pred' in df.columns else 0
    bot_ratio = round(bot_count / total_scanned * 100, 1) if total_scanned > 0 else 0
    overall_sentiment = float(df['sentiment_score'].mean()) if 'sentiment_score' in df.columns else 0.5
    
    radar_metrics = {}
    if 'is_bot_pred' in df.columns:
        humans_df = df[df['is_bot_pred'] == 0]
        bots_df = df[df['is_bot_pred'] == 1]
        
        radar_features = [
            'exclamation_density', 'follower_friend_ratio',
            'daily_post_rate', 'engagement_rate', 'link_count', 'is_default_avatar',
            'is_random_name', 'sentiment_score', 'topic_count', 'post_interval_variance'
        ]
        
        radar_metrics['humans'] = {f: float(humans_df[f].mean() if not humans_df.empty else 0) for f in radar_features}
        radar_metrics['bots'] = {f: float(bots_df[f].mean() if not bots_df.empty else 0) for f in radar_features}
    
    response = {
        "status": "success",
        "summary": {
            "total_scanned": total_scanned,
            "bot_count": bot_count,
            "bot_ratio": bot_ratio,
            "overall_sentiment": overall_sentiment
        },
        "radar_metrics": radar_metrics,
        "suspects": clean_for_json(df[df['is_bot_pred'] == 1].sort_values(by='bot_probability', ascending=False).head(5)) if 'is_bot_pred' in df.columns else [],
        "feed": clean_for_json(df.head(20))
    }
    return response

if __name__ == '__main__':
    # use_reloader=False prevents double-loading SnowNLP which causes MemoryError
    app.run(debug=True, port=5000, use_reloader=False)
