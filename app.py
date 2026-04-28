"""
Windows事件日志查看器 - Flask Web服务器
提供Web界面查看Windows事件日志，支持SQLite预处理、分页、缓存
"""
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
from evtx_parser import EvtxParser, get_evtx_categories, categorize_log_file
import os
import time
import threading
import hashlib
import shutil

load_dotenv()

app = Flask(__name__)

EVTX_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'evtx')
ARCHIVE_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'evtx_archive')
PAGE_SIZE = 200

# 文件变更版本号，用于全局同步
file_change_version = {'version': 0}
file_change_lock = threading.Lock()

def bump_version():
    """递增文件变更版本号"""
    with file_change_lock:
        file_change_version['version'] += 1

def ensure_archive_dir():
    """确保归档目录存在"""
    os.makedirs(ARCHIVE_DIRECTORY, exist_ok=True)

prebuild_threads = {}

@app.route('/')
def index():
    """主页,加载日志查看器页面"""
    return render_template('index.html')

@app.route('/api/files')
def get_files():
    """获取所有EVTX文件列表（平铺列表）"""
    categories = get_evtx_categories(EVTX_DIRECTORY)
    all_files = []
    
    for category, files in categories.items():
        for f in files:
            db_path = os.path.join(os.path.dirname(f['filepath']), 'db', 
                                   f"{os.path.splitext(f['filename'])[0]}.db")
            db_exists = os.path.exists(db_path)
            all_files.append({
                **f,
                'db_ready': db_exists
            })
    
    return jsonify({'status': 'success', 'files': all_files})

@app.route('/api/events')
def get_events():
    """
    从SQLite查询事件（分页，支持级别过滤、时间过滤、排序、事件ID过滤）
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
    
    event_id = request.args.get('event_id', '')
    
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
                         time_to=time_to if time_to else None, event_id=event_id if event_id else None,
                         sort_order=sort_order)
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
    """搜索事件，支持级别过滤、时间过滤、事件ID过滤、排序"""
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
    
    event_id = request.args.get('event_id', '')
    
    sort_order = request.args.get('sort_order', 'desc')
    
    if not filename or not keyword:
        return jsonify({'status': 'error', 'message': '请提供文件名和搜索关键词'}), 400
    
    filepath = os.path.join(EVTX_DIRECTORY, filename)
    if not os.path.exists(filepath):
        return jsonify({'status': 'error', 'message': f'文件不存在: {filename}'}), 404
    
    start_time = time.time()
    parser = EvtxParser(filepath)
    result = parser.search(keyword=keyword, page=page, page_size=page_size, levels=levels,
                          time_range=time_range, time_from=time_from if time_from else None,
                          time_to=time_to if time_to else None, event_id=event_id if event_id else None,
                          sort_order=sort_order)
    elapsed = time.time() - start_time
    
    return jsonify({
        'status': 'success',
        'filename': filename,
        **result,
        'query_time': round(elapsed, 4),
        'from_cache': elapsed < 0.01
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

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """上传EVTX文件，支持MD5去重检查"""
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': '未找到文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': '未选择文件'}), 400
    
    if not file.filename.lower().endswith('.evtx'):
        return jsonify({'status': 'error', 'message': '仅支持 .evtx 格式文件'}), 400
    
    # 计算MD5
    file_content = file.read()
    file.seek(0)
    md5_hash = hashlib.md5(file_content).hexdigest()
    
    # 检查MD5是否已存在
    existing_md5 = check_existing_md5(md5_hash)
    if existing_md5:
        return jsonify({
            'status': 'duplicate',
            'message': f'文件已存在: {existing_md5}',
            'md5': md5_hash,
            'existing_filename': existing_md5
        })
    
    # 保存文件
    filename = file.filename
    save_path = os.path.join(EVTX_DIRECTORY, filename)
    
    # 如果文件名冲突，添加序号
    if os.path.exists(save_path):
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(save_path):
            save_path = os.path.join(EVTX_DIRECTORY, f'{base}_{counter}{ext}')
            filename = f'{base}_{counter}{ext}'
            counter += 1
    
    with open(save_path, 'wb') as f:
        f.write(file_content)
    
    bump_version()
    return jsonify({
        'status': 'success',
        'message': f'上传成功: {filename}',
        'filename': filename,
        'md5': md5_hash,
        'size': os.path.getsize(save_path)
    })

def check_existing_md5(target_md5: str) -> str:
    """检查MD5是否已存在于evtx目录中，返回已存在的文件名或None"""
    if not os.path.exists(EVTX_DIRECTORY):
        return None
    
    for filename in os.listdir(EVTX_DIRECTORY):
        if not filename.lower().endswith('.evtx'):
            continue
        filepath = os.path.join(EVTX_DIRECTORY, filename)
        file_md5 = hashlib.md5(open(filepath, 'rb').read()).hexdigest()
        if file_md5 == target_md5:
            return filename
    return None

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

@app.route('/api/event_ids')
def get_event_ids():
    """获取事件ID统计（按出现次数排序）"""
    filename = request.args.get('filename')
    limit = int(request.args.get('limit', 20))
    
    if not filename:
        return jsonify({'status': 'error', 'message': '请提供文件名'}), 400
    
    filepath = os.path.join(EVTX_DIRECTORY, filename)
    if not os.path.exists(filepath):
        return jsonify({'status': 'error', 'message': f'文件不存在: {filename}'}), 404
    
    start_time = time.time()
    parser = EvtxParser(filepath)
    parser.ensure_db()
    
    conn = sqlite3.connect(parser.db_path)
    rows = conn.execute(
        f"SELECT event_id, COUNT(*) as cnt FROM events GROUP BY event_id ORDER BY cnt DESC LIMIT ?",
        [limit]
    ).fetchall()
    conn.close()
    
    result = [{'event_id': row[0], 'count': row[1]} for row in rows]
    elapsed = time.time() - start_time
    
    return jsonify({
        'status': 'success',
        'event_ids': result,
        'query_time': round(elapsed, 4)
    })

@app.route('/api/file/delete', methods=['POST'])
def delete_file():
    """删除EVTX文件及其数据库"""
    data = request.get_json() or {}
    filename = data.get('filename')
    
    if not filename:
        return jsonify({'status': 'error', 'message': '请提供文件名'}), 400
    
    filepath = os.path.join(EVTX_DIRECTORY, filename)
    if not os.path.exists(filepath):
        return jsonify({'status': 'error', 'message': f'文件不存在: {filename}'}), 404
    
    try:
        # 删除EVTX文件
        os.remove(filepath)
        
        # 删除对应的数据库文件
        db_path = os.path.join(EVTX_DIRECTORY, 'db', f"{os.path.splitext(filename)[0]}.db")
        if os.path.exists(db_path):
            os.remove(db_path)
        # 删除WAL/SHM文件
        for suffix in ['-wal', '-shm']:
            wal_path = db_path + suffix
            if os.path.exists(wal_path):
                os.remove(wal_path)
        
        bump_version()
        return jsonify({'status': 'success', 'message': f'已删除: {filename}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'删除失败: {str(e)}'}), 500

@app.route('/api/file/archive', methods=['POST'])
def archive_file():
    """归档EVTX文件（移动到归档目录）"""
    data = request.get_json() or {}
    filename = data.get('filename')
    
    if not filename:
        return jsonify({'status': 'error', 'message': '请提供文件名'}), 400
    
    filepath = os.path.join(EVTX_DIRECTORY, filename)
    if not os.path.exists(filepath):
        return jsonify({'status': 'error', 'message': f'文件不存在: {filename}'}), 404
    
    ensure_archive_dir()
    
    try:
        # 生成归档文件名（带时间戳）
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        base, ext = os.path.splitext(filename)
        archive_name = f'{base}_{timestamp}{ext}'
        archive_path = os.path.join(ARCHIVE_DIRECTORY, archive_name)
        
        # 如果归档文件已存在，添加序号
        if os.path.exists(archive_path):
            counter = 1
            while os.path.exists(archive_path):
                archive_name = f'{base}_{timestamp}_{counter}{ext}'
                archive_path = os.path.join(ARCHIVE_DIRECTORY, archive_name)
                counter += 1
        
        # 移动EVTX文件
        shutil.move(filepath, archive_path)
        
        # 移动数据库文件（如果存在）
        db_path = os.path.join(EVTX_DIRECTORY, 'db', f"{os.path.splitext(filename)[0]}.db")
        if os.path.exists(db_path):
            archive_db_name = f"{os.path.splitext(filename)[0]}_{timestamp}.db"
            archive_db_path = os.path.join(ARCHIVE_DIRECTORY, archive_db_name)
            shutil.move(db_path, archive_db_path)
            # 移动WAL/SHM文件
            for suffix in ['-wal', '-shm']:
                wal_path = db_path + suffix
                if os.path.exists(wal_path):
                    shutil.move(wal_path, archive_db_path + suffix)
        
        bump_version()
        return jsonify({
            'status': 'success',
            'message': f'已归档: {filename} -> {archive_name}',
            'archive_name': archive_name
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'归档失败: {str(e)}'}), 500

@app.route('/api/file/restore', methods=['POST'])
def restore_file():
    """从归档目录恢复文件"""
    data = request.get_json() or {}
    filename = data.get('filename')
    
    if not filename:
        return jsonify({'status': 'error', 'message': '请提供文件名'}), 400
    
    filepath = os.path.join(ARCHIVE_DIRECTORY, filename)
    if not os.path.exists(filepath):
        return jsonify({'status': 'error', 'message': f'归档文件不存在: {filename}'}), 404
    
    try:
        # 恢复EVTX文件
        dest_path = os.path.join(EVTX_DIRECTORY, filename)
        if os.path.exists(dest_path):
            return jsonify({'status': 'error', 'message': f'目标文件已存在: {filename}'}), 409
        
        shutil.move(filepath, dest_path)
        
        # 恢复数据库文件（如果存在）
        db_name = os.path.splitext(filename)[0] + '.db'
        archive_db_path = os.path.join(ARCHIVE_DIRECTORY, db_name)
        if os.path.exists(archive_db_path):
            dest_db_path = os.path.join(EVTX_DIRECTORY, 'db', db_name)
            shutil.move(archive_db_path, dest_db_path)
            for suffix in ['-wal', '-shm']:
                wal_path = archive_db_path + suffix
                if os.path.exists(wal_path):
                    shutil.move(wal_path, dest_db_path + suffix)
        
        bump_version()
        return jsonify({'status': 'success', 'message': f'已恢复: {filename}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'恢复失败: {str(e)}'}), 500

@app.route('/api/archive/list')
def list_archive():
    """获取归档文件列表"""
    ensure_archive_dir()
    archives = []
    for f in sorted(os.listdir(ARCHIVE_DIRECTORY)):
        filepath = os.path.join(ARCHIVE_DIRECTORY, f)
        if f.lower().endswith('.evtx'):
            archives.append({
                'filename': f,
                'size': os.path.getsize(filepath),
                'archived_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(filepath)))
            })
    return jsonify({'status': 'success', 'archives': archives})

@app.route('/api/sync/version')
def get_sync_version():
    """获取当前文件变更版本号"""
    return jsonify({'status': 'success', 'version': file_change_version['version']})

@app.route('/api/sync/poll')
def poll_sync():
    """轮询检查文件变更（长轮询）"""
    client_version = int(request.args.get('version', 0))
    timeout = int(request.args.get('timeout', 25))
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        if file_change_version['version'] != client_version:
            return jsonify({
                'status': 'changed',
                'version': file_change_version['version']
            })
        time.sleep(0.5)
    
    return jsonify({
        'status': 'timeout',
        'version': file_change_version['version']
    })

if __name__ == '__main__':
    app.run(
        host=os.getenv('FLASK_HOST', '127.0.0.1'),
        port=int(os.getenv('FLASK_PORT', 5000)),
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
