"""
Windows事件日志查看器 - Flask Web服务器
提供Web界面查看Windows事件日志，支持SQLite预处理、分页、缓存
"""
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
from evtx_parser import EvtxParser, get_evtx_categories
import os
import time
import threading

load_dotenv()

app = Flask(__name__)

EVTX_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'evtx')
PAGE_SIZE = 200

prebuild_threads = {}

@app.route('/')
def index():
    """主页,加载日志查看器页面"""
    return render_template('index.html')

@app.route('/api/files')
def get_files():
    """获取所有EVTX文件列表（按类别分组）"""
    categories = get_evtx_categories(EVTX_DIRECTORY)
    result = {'status': 'success', 'categories': {}}
    
    for category, files in categories.items():
        result['categories'][category] = []
        for f in files:
            db_path = os.path.join(os.path.dirname(f['filepath']), 'db', 
                                   f"{os.path.splitext(f['filename'])[0]}.db")
            db_exists = os.path.exists(db_path)
            result['categories'][category].append({
                **f,
                'db_ready': db_exists
            })
    
    return jsonify(result)

@app.route('/api/events')
def get_events():
    """
    从SQLite查询事件（分页，支持级别过滤、时间过滤、排序）
    """
    filename = request.args.get('filename')
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', PAGE_SIZE))
    levels_param = request.args.get('levels', '')
    levels = [l for l in levels_param.split(',') if l] if levels_param else None
    
    time_range_param = request.args.get('time_range')
    time_range = int(time_range_param) if time_range_param is not None else None
    
    time_from = request.args.get('time_from', '')
    time_to = request.args.get('time_to', '')
    
    sort_order = request.args.get('sort_order', 'desc')
    
    if not filename:
        return jsonify({'status': 'error', 'message': '请提供文件名'}), 400
    
    filepath = os.path.join(EVTX_DIRECTORY, filename)
    if not os.path.exists(filepath):
        return jsonify({'status': 'error', 'message': f'文件不存在: {filename}'}), 404
    
    start_time = time.time()
    parser = EvtxParser(filepath)
    result = parser.query(page=page, page_size=page_size, levels=levels, 
                         time_range=time_range, time_from=time_from if time_from else None,
                         time_to=time_to if time_to else None, sort_order=sort_order)
    elapsed = time.time() - start_time
    
    return jsonify({
        'status': 'success',
        'filename': filename,
        **result,
        'query_time': round(elapsed, 4),
        'from_cache': elapsed < 0.01
    })

@app.route('/api/search')
def search_events():
    """搜索事件，支持级别过滤、时间过滤、排序"""
    filename = request.args.get('filename')
    keyword = request.args.get('keyword', '')
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', PAGE_SIZE))
    levels_param = request.args.get('levels', '')
    levels = [l for l in levels_param.split(',') if l] if levels_param else None
    
    time_range_param = request.args.get('time_range')
    time_range = int(time_range_param) if time_range_param is not None else None
    
    time_from = request.args.get('time_from', '')
    time_to = request.args.get('time_to', '')
    
    sort_order = request.args.get('sort_order', 'desc')
    
    if not filename or not keyword:
        return jsonify({'status': 'error', 'message': '请提供文件名和搜索关键词'}), 400
    
    filepath = os.path.join(EVTX_DIRECTORY, filename)
    if not os.path.exists(filepath):
        return jsonify({'status': 'error', 'message': f'文件不存在: {filename}'}), 404
    
    parser = EvtxParser(filepath)
    result = parser.search(keyword=keyword, page=page, page_size=page_size, levels=levels,
                          time_range=time_range, time_from=time_from if time_from else None,
                          time_to=time_to if time_to else None, sort_order=sort_order)
    
    return jsonify({
        'status': 'success',
        'filename': filename,
        **result
    })

@app.route('/api/build')
def build_db():
    """后台构建数据库"""
    filename = request.args.get('filename')
    force = request.args.get('force', 'false').lower() == 'true'
    if not filename:
        return jsonify({'status': 'error', 'message': '请提供文件名'}), 400
    
    filepath = os.path.join(EVTX_DIRECTORY, filename)
    if not os.path.exists(filepath):
        return jsonify({'status': 'error', 'message': f'文件不存在: {filename}'}), 404
    
    if filename in prebuild_threads:
        return jsonify({'status': 'building', 'message': '正在构建中，请稍候'})
    
    # 使用Event来标记构建完成，避免线程过早从字典中移除
    import threading
    done_event = threading.Event()
    prebuild_threads[filename] = {'thread': None, 'done': done_event}
    
    def do_build():
        try:
            parser = EvtxParser(filepath)
            if force:
                if os.path.exists(parser.db_path):
                    os.remove(parser.db_path)
            parser.ensure_db()
        except Exception as e:
            print(f"构建失败: {e}")
        finally:
            done_event.set()
    
    t = threading.Thread(target=do_build, daemon=True)
    prebuild_threads[filename]['thread'] = t
    t.start()
    
    return jsonify({'status': 'started', 'message': '开始构建数据库'})

@app.route('/api/build/status')
def build_status():
    """查询构建状态"""
    filename = request.args.get('filename')
    info = prebuild_threads.get(filename)
    if info and not info['done'].is_set():
        return jsonify({'status': 'building', 'progress': '正在构建...'})
    # 构建完成或不存在，清理记录
    if filename in prebuild_threads:
        del prebuild_threads[filename]
    return jsonify({'status': 'idle'})

@app.route('/api/fields')
def get_fields():
    """获取可用的字段列表（包含所有EVTX System字段）"""
    fields = [
        {'id': 'RecordID', 'name': '记录ID', 'default': True},
        {'id': 'EventID', 'name': '事件ID', 'default': True},
        {'id': 'Version', 'name': '版本', 'default': False},
        {'id': 'Level', 'name': '级别', 'default': True},
        {'id': 'Task', 'name': '任务', 'default': False},
        {'id': 'Opcode', 'name': '操作码', 'default': False},
        {'id': 'Keywords', 'name': '关键字', 'default': False},
        {'id': 'TimeCreated', 'name': '创建时间', 'default': True},
        {'id': 'TimeCreatedRaw', 'name': '原始时间', 'default': False},
        {'id': 'EventRecordID', 'name': '事件记录ID', 'default': False},
        {'id': 'CorrelationActivityID', 'name': '关联活动ID', 'default': False},
        {'id': 'CorrelationRelatedActivityID', 'name': '关联相关活动ID', 'default': False},
        {'id': 'ExecutionProcessID', 'name': '进程ID', 'default': False},
        {'id': 'ExecutionThreadID', 'name': '线程ID', 'default': False},
        {'id': 'Provider', 'name': '提供程序', 'default': True},
        {'id': 'ProviderGUID', 'name': '提供程序GUID', 'default': False},
        {'id': 'Channel', 'name': '通道', 'default': True},
        {'id': 'Computer', 'name': '计算机', 'default': True},
        {'id': 'UserID', 'name': '用户ID', 'default': False},
        {'id': 'Message', 'name': '消息', 'default': True},
        {'id': 'EventData', 'name': '事件数据', 'default': False},
        {'id': 'RawXML', 'name': '原始XML', 'default': False}
    ]
    return jsonify({'status': 'success', 'fields': fields})

if __name__ == '__main__':
    app.run(
        host=os.getenv('FLASK_HOST', '127.0.0.1'),
        port=int(os.getenv('FLASK_PORT', 5000)),
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
