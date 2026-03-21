from flask import Flask, render_template, request, jsonify
from bot_pipeline import run_pipeline
import traceback
import topic_db

from response_builder import build_topic_response, analyze_single_user
from logger import logger

app = Flask(__name__)

# ===================== Routes =====================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/history', methods=['GET'])
def get_history():
    """获取所有历史话题的列表"""
    try:
        topics = topic_db.get_all_topics()
        return jsonify({"status": "success", "topics": topics})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/delete_topic', methods=['POST'])
def delete_topic():
    """删除特定话题的数据"""
    data = request.json
    topic = data.get('topic', '')
    if not topic:
        return jsonify({"error": "缺少话题参数"}), 400
    try:
        topic_db.clear_topic(topic)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/detect', methods=['POST'])
def detect_bots():
    """话题检测 API：输入话题关键词，返回水军检测结果（支持断点续爬及历史加载）"""
    data = request.json
    topic = data.get('topic', '')
    limit = int(data.get('limit', 15))
    continue_mode = bool(data.get('continue', False))
    action = data.get('action', 'fetch')  # 'fetch' or 'load'
    cookie = data.get('cookie', '')  # 用户自带 Cookie（可选）

    if not topic:
        return jsonify({"error": "请输入有效的微博话题或关键词"}), 400

    try:
        if action == 'load':
            df = topic_db.load_all_posts(topic)
            if df.empty:
                return jsonify({"error": f"未找到话题 '{topic}' 的历史数据"}), 404
            meta = topic_db.get_topic_meta(topic)
            crawl_info = {'new_fetched': 0, 'total_fetched': meta['total_fetched'], 'has_more': True}
        else:
            df, crawl_info = run_pipeline(topic, limit, continue_mode=continue_mode, cookie=cookie)
            
        if df.empty and action != 'load':
            return jsonify({"error": "未获取到任何数据，可能是被反爬或数据为空。"})

        response = build_topic_response(df)
        response['crawl_info'] = crawl_info
        return jsonify(response)
    except Exception as e:
        logger.exception(f"话题检测接口执行失败: {topic}")
        tb = traceback.format_exc()
        return jsonify({"error": f"执行失败: {str(e)}\n\nTRACEBACK:\n{tb}"}), 500


@app.route('/api/check_user', methods=['POST'])
def check_user():
    """单账号检测 API：输入 UID，返回该用户的可疑度评分和特征"""
    data = request.json
    uid = data.get('uid', '')
    cookie = data.get('cookie', '')

    if not uid:
        return jsonify({"error": "请输入有效的微博用户 UID"}), 400

    try:
        result = analyze_single_user(uid, cookie)
        return jsonify(result)
    except Exception as e:
        logger.exception(f"单账号分析失败 UID={uid}")
        return jsonify({"error": f"分析失败: {str(e)}"}), 500


# ===================== Entry =====================

if __name__ == '__main__':
    # host='0.0.0.0' 是云端部署的关键，允许外网通过公网 IP 访问
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
