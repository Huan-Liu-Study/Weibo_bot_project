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


# ===================== Labeling API =====================

from label_service import get_label_queue, submit_label, get_label_stats, get_labeled_queue, mark_as_trained
from model_service import get_model_info, retrain_model

@app.route('/api/label/queue', methods=['GET'])
def label_queue():
    """获取待标注用户队列"""
    try:
        topic = request.args.get('topic', '')
        page = int(request.args.get('page', 1))
        result = get_label_queue(topic=topic or None, page=page)
        result['stats'] = get_label_stats()
        return jsonify(result)
    except Exception as e:
        logger.exception("获取标注队列失败")
        return jsonify({"error": str(e)}), 500


@app.route('/api/label/submit', methods=['POST'])
def label_submit():
    """提交单个用户的标注结果"""
    data = request.json
    uid = data.get('user_id', '')
    label = int(data.get('label', 2))
    topic = data.get('topic', '')
    ai_score = float(data.get('ai_pred_score', 0.5))
    features = data.get('features', {})

    if not uid:
        return jsonify({"error": "缺少 user_id"}), 400
    if label not in [-1, 0, 1, 2, 3, 4]:
        return jsonify({"error": "label 必须为 -1 到 4"}), 400

    try:
        result = submit_label(uid, label, topic, ai_score, features)
        return jsonify(result)
    except Exception as e:
        logger.exception(f"标注提交失败 UID={uid}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/label/delete/<user_id>', methods=['DELETE'])
def label_delete_user(user_id):
    """永久删除该用户的所有数据"""
    try:
        from label_service import delete_user
        success = delete_user(user_id)
        return jsonify({"status": "success", "deleted_uid": user_id})
    except Exception as e:
        logger.exception(f"删除用户 {user_id} 失败")
        return jsonify({"error": str(e)}), 500

# ==================== 媒体白名单库 API ====================
@app.route('/api/media/list', methods=['GET'])
def api_media_list():
    """获取所有媒体白名单"""
    try:
        import media_db
        res = media_db.get_all_media()
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/media/add', methods=['POST'])
def api_media_add():
    """手动添加媒体白名单"""
    data = request.json or {}
    uid = str(data.get('user_id', '')).strip()
    name = str(data.get('screen_name', '')).strip()
    if not uid:
        return jsonify({"error": "缺失 user_id"}), 400
    try:
        import media_db
        media_db.add_media_account(uid, name)
        return jsonify({"status": "success", "added_uid": uid})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/media/delete/<user_id>', methods=['DELETE'])
def api_media_delete(user_id):
    """从媒体白名单移除"""
    try:
        import media_db
        media_db.delete_media_account(user_id)
        return jsonify({"status": "success", "deleted_uid": str(user_id)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 标注模块管理员密码 (毕设级别，简单明文即可)
LABEL_ADMIN_PASSWORD = 'botshield2026'

@app.route('/api/label/auth', methods=['POST'])
def label_auth():
    """验证标注模块管理员密码"""
    data = request.json
    pwd = data.get('password', '')
    if pwd == LABEL_ADMIN_PASSWORD:
        return jsonify({'status': 'success'})
    return jsonify({'status': 'fail', 'error': '密码错误'}), 403


@app.route('/api/label/labeled', methods=['GET'])
def label_labeled():
    """获取已标注但未训练的用户列表"""
    try:
        topic = request.args.get('topic', '')
        page = int(request.args.get('page', 1))
        result = get_labeled_queue(topic=topic or None, page=page)
        return jsonify(result)
    except Exception as e:
        logger.exception("获取已标注列表失败")
        return jsonify({"error": str(e)}), 500


@app.route('/api/model/info', methods=['GET'])
def model_info():
    """获取当前模型信息和特征权重"""
    try:
        return jsonify(get_model_info())
    except Exception as e:
        logger.exception("获取模型信息失败")
        return jsonify({"error": str(e)}), 500


@app.route('/api/model/retrain', methods=['POST'])
def model_retrain():
    """触发模型重训练"""
    try:
        result = retrain_model()
        # 训练成功后标记已标注数据为“已训练”
        if result.get('status') == 'success':
            trained_count = mark_as_trained()
            result['trained_marked'] = trained_count
        return jsonify(result)
    except Exception as e:
        logger.exception("模型重训练失败")
        return jsonify({"error": str(e)}), 500


# ===================== Entry =====================

if __name__ == '__main__':
    # host='0.0.0.0' 是云端部署的关键，允许外网通过公网 IP 访问
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
