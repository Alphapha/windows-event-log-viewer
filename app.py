"""
Windows事件日志查看器 - Flask Web服务器
提供Web界面查看Windows事件日志
"""
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
from evtx_parser import EvtxParser, get_evtx_files
import os

load_dotenv()

app = Flask(__name__)

EVTX_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'evtx')

@app.route('/')
def index():
    """主页,加载日志查看器页面"""
    return render_template('index.html')

@app.route('/api/files')
def get_files():
    """获取所有EVTX文件列表"""
    files = get_evtx_files(EVTX_DIRECTORY)
    return jsonify({
        'status': 'success',
        'files': files
    })

@app.route('/api/events')
def get_events():
    """获取指定EVTX文件的事件列表"""
    filename = request.args.get('filename')
    if not filename:
        return jsonify({
            'status': 'error',
            'message': '请提供文件名'
        }), 400
    
    filepath = os.path.join(EVTX_DIRECTORY, filename)
    
    if not os.path.exists(filepath):
        return jsonify({
            'status': 'error',
            'message': f'文件不存在: {filename}'
        }), 404
    
    parser = EvtxParser(filepath)
    events = parser.parse()
    
    return jsonify({
        'status': 'success',
        'filename': filename,
        'total': len(events),
        'events': events
    })

@app.route('/api/fields')
def get_fields():
    """获取可用的字段列表"""
    fields = [
        {'id': 'RecordID', 'name': '记录ID', 'default': True},
        {'id': 'EventID', 'name': '事件ID', 'default': True},
        {'id': 'TimeCreated', 'name': '创建时间', 'default': True},
        {'id': 'Level', 'name': '级别', 'default': True},
        {'id': 'Provider', 'name': '提供程序', 'default': True},
        {'id': 'Channel', 'name': '通道', 'default': False},
        {'id': 'Computer', 'name': '计算机', 'default': False},
        {'id': 'UserID', 'name': '用户ID', 'default': False},
        {'id': 'Message', 'name': '消息', 'default': True},
        {'id': 'EventData', 'name': '事件数据', 'default': False},
        {'id': 'RawXML', 'name': '原始XML', 'default': False}
    ]
    return jsonify({
        'status': 'success',
        'fields': fields
    })

if __name__ == '__main__':
    app.run(
        host=os.getenv('FLASK_HOST', '127.0.0.1'),
        port=int(os.getenv('FLASK_PORT', 5000)),
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
