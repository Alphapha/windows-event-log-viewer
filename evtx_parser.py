"""
EVTX日志解析模块 - 高性能SQLite优化版
首次解析后存入SQLite数据库，后续查询毫秒级响应
"""
import xml.etree.ElementTree as ET
from Evtx.Evtx import FileHeader
from datetime import datetime
from typing import List, Dict, Any, Generator
import os
import json
import hashlib
import sqlite3
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import multiprocessing

NS = 'http://schemas.microsoft.com/win/2004/08/events/event'

LOG_CATEGORIES = {
    '安全日志': ['Security'],
    '系统日志': ['System'],
    '应用程序日志': ['Application'],
    'Setup日志': ['Setup'],
    'Forwarded日志': ['ForwardedEvents']
}


def categorize_log_file(filename: str) -> str:
    """根据文件名判断日志类别"""
    filename_lower = filename.lower()
    if 'security' in filename_lower:
        return '安全日志'
    elif 'system' in filename_lower:
        return '系统日志'
    elif 'application' in filename_lower or 'app' in filename_lower:
        return '应用程序日志'
    elif 'setup' in filename_lower:
        return 'Setup日志'
    else:
        return '其他日志'


def init_db(db_path: str):
    """初始化SQLite数据库"""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id TEXT,
            event_id TEXT,
            time_created TEXT,
            level TEXT,
            provider TEXT,
            channel TEXT,
            computer TEXT,
            user_id TEXT,
            message TEXT,
            event_data TEXT,
            raw_xml TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_event_id ON events(event_id);
        CREATE INDEX IF NOT EXISTS idx_time_created ON events(time_created);
        CREATE INDEX IF NOT EXISTS idx_level ON events(level);
        CREATE INDEX IF NOT EXISTS idx_provider ON events(provider);
    ''')
    conn.commit()
    return conn


def get_db_path(evtx_path: str, db_dir: str = None) -> str:
    """获取数据库文件路径"""
    db_dir = db_dir or os.path.join(os.path.dirname(evtx_path), 'db')
    os.makedirs(db_dir, exist_ok=True)
    filename = os.path.basename(evtx_path)
    return os.path.join(db_dir, f"{os.path.splitext(filename)[0]}.db")


def evtx_needs_update(evtx_path: str, db_path: str) -> bool:
    """检查EVTX文件是否需要更新数据库"""
    if not os.path.exists(db_path):
        return True
    evtx_mtime = os.path.getmtime(evtx_path)
    db_mtime = os.path.getmtime(db_path)
    return evtx_mtime > db_mtime


def parse_single_record(args):
    """解析单个XML记录(用于多进程)"""
    xml_string = args[0]
    try:
        root = ET.fromstring(xml_string)
        system = root.find(f'.//{{{NS}}}System')
        if system is None:
            return None

        def find_text(tag):
            elem = system.find(f'{{{NS}}}{tag}')
            return elem.text if elem is not None else ''

        def find_attr(tag, attr):
            elem = system.find(f'{{{NS}}}{tag}')
            return elem.get(attr, '') if elem is not None else ''

        time_created = ''
        tc = system.find(f'{{{NS}}}TimeCreated')
        if tc is not None:
            utc_time = tc.get('SystemTime')
            if utc_time:
                try:
                    dt = datetime.fromisoformat(utc_time.replace('Z', '+00:00'))
                    time_created = dt.strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    pass

        level_map = {'1': '严重', '2': '错误', '3': '警告', '4': '信息', '5': '详细'}
        level_elem = system.find(f'{{{NS}}}Level')
        level = level_map.get(level_elem.text, level_elem.text) if level_elem is not None else ''

        event_data = {}
        event_data_elem = root.find(f'.//{{{NS}}}EventData')
        if event_data_elem is not None:
            for data in event_data_elem.findall(f'{{{NS}}}Data'):
                name = data.get('Name', '')
                value = data.text or ''
                if name:
                    event_data[name] = value
                else:
                    event_data[f'Data_{len(event_data)}'] = value

        return {
            'RecordID': find_text('EventRecordID'),
            'EventID': find_text('EventID'),
            'TimeCreated': time_created,
            'Level': level,
            'Provider': find_attr('Provider', 'Name'),
            'Channel': find_text('Channel'),
            'Computer': find_text('Computer'),
            'UserID': (system.find(f'{{{NS}}}Security') or {}).get('UserID', ''),
            'Message': find_text('Message'),
            'EventData': json.dumps(event_data, ensure_ascii=False) if event_data else '',
            'RawXML': xml_string
        }
    except ET.ParseError:
        return None


class EvtxParser:
    """EVTX文件解析器 - SQLite高性能版"""

    def __init__(self, evtx_path: str):
        self.evtx_path = evtx_path
        self.db_path = get_db_path(evtx_path)

    def _build_db(self, use_multiprocess: bool = True) -> int:
        """
        从EVTX文件构建SQLite数据库
        返回: 事件数量
        """
        # 先初始化数据库（创建表结构）
        conn = init_db(self.db_path)
        c = conn.cursor()
        c.execute("DELETE FROM events")
        conn.commit()
        conn.close()

        print(f"[{os.path.basename(self.evtx_path)}] 开始解析...")
        start = time.time()

        with open(self.evtx_path, 'rb') as f:
            buf = f.read()
            header = FileHeader(buf, 0)

            xml_records = []
            for chunk in header.chunks():
                for record in chunk.records():
                    try:
                        xml_records.append(record.xml())
                    except Exception:
                        continue

        extract_time = time.time() - start
        print(f"  提取XML: {len(xml_records)}条, 耗时{extract_time:.2f}秒")

        parsed_records = []
        batch_size = 1000

        if use_multiprocess and len(xml_records) > 200:
            cpu_count = min(multiprocessing.cpu_count(), 8)
            chunk_size = max(100, len(xml_records) // (cpu_count * 2))

            with ProcessPoolExecutor(max_workers=cpu_count) as executor:
                args_list = [(xml,) for xml in xml_records]
                for result in executor.map(parse_single_record, args_list, chunksize=chunk_size):
                    if result is not None:
                        parsed_records.append(result)
                        if len(parsed_records) >= batch_size:
                            batch = parsed_records
                            parsed_records = []
                            self._insert_batch_to_db(batch)
        else:
            for xml in xml_records:
                result = parse_single_record((xml,))
                if result is not None:
                    parsed_records.append(result)
                    if len(parsed_records) >= batch_size:
                        batch = parsed_records
                        parsed_records = []
                        self._insert_batch_to_db(batch)

        if parsed_records:
            self._insert_batch_to_db(parsed_records)

        conn = sqlite3.connect(self.db_path)
        total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        conn.close()
        total_time = time.time() - start
        print(f"  数据库构建完成: {total}条, 总耗时{total_time:.2f}秒")
        return total

    def _insert_batch_to_db(self, batch):
        """批量插入数据到SQLite（在主进程执行）"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.executemany('''
            INSERT INTO events (record_id, event_id, time_created, level, provider, channel, computer, user_id, message, event_data, raw_xml)
            VALUES (:RecordID, :EventID, :TimeCreated, :Level, :Provider, :Channel, :Computer, :UserID, :Message, :EventData, :RawXML)
        ''', batch)
        conn.commit()
        conn.close()

    def ensure_db(self, use_multiprocess: bool = True) -> int:
        """
        确保数据库是最新的，如果需要则构建
        返回: 事件数量
        """
        if evtx_needs_update(self.evtx_path, self.db_path):
            return self._build_db(use_multiprocess)
        else:
            conn = sqlite3.connect(self.db_path)
            total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            conn.close()
            return total

    def query(self, page: int = 1, page_size: int = 200) -> Dict[str, Any]:
        """
        从数据库查询事件（分页）
        """
        self.ensure_db()
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        total = c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        offset = (page - 1) * page_size

        rows = c.execute(
            "SELECT * FROM events ORDER BY id LIMIT ? OFFSET ?",
            (page_size, offset)
        ).fetchall()

        events = []
        for row in rows:
            events.append({
                'RecordID': row['record_id'] or '',
                'EventID': row['event_id'] or '',
                'TimeCreated': row['time_created'] or '',
                'Level': row['level'] or '',
                'Provider': row['provider'] or '',
                'Channel': row['channel'] or '',
                'Computer': row['computer'] or '',
                'UserID': row['user_id'] or '',
                'Message': row['message'] or '',
                'EventData': json.loads(row['event_data']) if row['event_data'] else {},
                'RawXML': row['raw_xml'] or ''
            })

        conn.close()
        return {
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size if total > 0 else 0,
            'events': events
        }

    def search(self, keyword: str, page: int = 1, page_size: int = 200) -> Dict[str, Any]:
        """搜索事件"""
        self.ensure_db()
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        like = f'%{keyword}%'
        total = c.execute(
            "SELECT COUNT(*) FROM events WHERE event_id LIKE ? OR provider LIKE ? OR message LIKE ?",
            (like, like, like)
        ).fetchone()[0]
        offset = (page - 1) * page_size

        rows = c.execute('''
            SELECT * FROM events WHERE event_id LIKE ? OR provider LIKE ? OR message LIKE ?
            ORDER BY id LIMIT ? OFFSET ?
        ''', (like, like, like, page_size, offset)).fetchall()

        events = []
        for row in rows:
            events.append({
                'RecordID': row['record_id'] or '',
                'EventID': row['event_id'] or '',
                'TimeCreated': row['time_created'] or '',
                'Level': row['level'] or '',
                'Provider': row['provider'] or '',
                'Channel': row['channel'] or '',
                'Computer': row['computer'] or '',
                'UserID': row['user_id'] or '',
                'Message': row['message'] or '',
                'EventData': json.loads(row['event_data']) if row['event_data'] else {},
                'RawXML': row['raw_xml'] or ''
            })

        conn.close()
        return {
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size if total > 0 else 0,
            'events': events
        }


def get_evtx_files(directory: str) -> List[Dict[str, str]]:
    """获取指定目录下的所有EVTX文件"""
    evtx_files = []
    if not os.path.exists(directory):
        return evtx_files
    for filename in os.listdir(directory):
        if filename.endswith('.evtx'):
            filepath = os.path.join(directory, filename)
            category = categorize_log_file(filename)
            evtx_files.append({
                'filename': filename,
                'filepath': filepath,
                'size': os.path.getsize(filepath),
                'category': category
            })
    return sorted(evtx_files, key=lambda x: (x['category'], x['filename']))


def get_evtx_categories(directory: str) -> Dict[str, List[Dict[str, str]]]:
    """获取按类别分组的EVTX文件"""
    files = get_evtx_files(directory)
    categories = {}
    for file in files:
        category = file['category']
        if category not in categories:
            categories[category] = []
        categories[category].append(file)
    return categories
