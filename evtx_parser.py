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
            version TEXT,
            level TEXT,
            level_text TEXT,
            task TEXT,
            opcode TEXT,
            keywords TEXT,
            time_created TEXT,
            time_created_raw TEXT,
            event_record_id TEXT,
            correlation_activity_id TEXT,
            correlation_related_activity_id TEXT,
            execution_process_id TEXT,
            execution_thread_id TEXT,
            provider TEXT,
            provider_guid TEXT,
            channel TEXT,
            computer TEXT,
            user_id TEXT,
            message TEXT,
            event_data TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_event_id ON events(event_id);
        CREATE INDEX IF NOT EXISTS idx_time_created ON events(time_created);
        CREATE INDEX IF NOT EXISTS idx_level ON events(level);
        CREATE INDEX IF NOT EXISTS idx_provider ON events(provider);
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
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
        time_created_raw = ''
        tc = system.find(f'{{{NS}}}TimeCreated')
        if tc is not None:
            utc_time = tc.get('SystemTime')
            if utc_time:
                time_created_raw = utc_time
                try:
                    dt = datetime.fromisoformat(utc_time.replace('Z', '+00:00'))
                    time_created = dt.strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    pass

        level_map = {'0': '', '1': '严重', '2': '错误', '3': '警告', '4': '信息', '5': '详细'}
        level_raw = find_text('Level')
        level = level_map.get(level_raw, level_raw)

        correlation = system.find(f'{{{NS}}}Correlation')
        corr_activity_id = correlation.get('ActivityID', '') if correlation is not None else ''
        corr_related_activity_id = correlation.get('RelatedActivityID', '') if correlation is not None else ''

        execution = system.find(f'{{{NS}}}Execution')
        exec_process_id = execution.get('ProcessID', '') if execution is not None else ''
        exec_thread_id = execution.get('ThreadID', '') if execution is not None else ''

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

        rendering_info = root.find(f'.//{{{NS}}}RenderingInfo')
        message = ''
        if rendering_info is not None:
            msg_elem = rendering_info.find(f'{{{NS}}}Message')
            message = msg_elem.text or '' if msg_elem is not None else ''
        if not message:
            message = find_text('Message')

        return {
            'RecordID': find_text('EventRecordID'),
            'EventID': find_text('EventID'),
            'Version': find_text('Version'),
            'Level': level,
            'LevelText': level_raw,
            'Task': find_text('Task'),
            'Opcode': find_text('Opcode'),
            'Keywords': find_text('Keywords'),
            'TimeCreated': time_created,
            'TimeCreatedRaw': time_created_raw,
            'EventRecordID': find_text('EventRecordID'),
            'CorrelationActivityID': corr_activity_id,
            'CorrelationRelatedActivityID': corr_related_activity_id,
            'ExecutionProcessID': exec_process_id,
            'ExecutionThreadID': exec_thread_id,
            'Provider': find_attr('Provider', 'Name'),
            'ProviderGUID': find_attr('Provider', 'Guid'),
            'Channel': find_text('Channel'),
            'Computer': find_text('Computer'),
            'UserID': (system.find(f'{{{NS}}}Security') or {}).get('UserID', ''),
            'Message': message,
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
        # 创建数据库并初始化表结构
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        
        # 清理可能残留的WAL/SHM文件
        for suffix in ['-wal', '-shm']:
            path = self.db_path + suffix
            if os.path.exists(path):
                os.remove(path)
        
        # 使用单一连接贯穿整个构建过程，避免WAL多连接可见性问题
        conn = init_db(self.db_path)
        c = conn.cursor()

        print(f"[{os.path.basename(self.evtx_path)}] 开始解析...")
        start = time.time()

        try:
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
                                self._insert_batch_to_cursor(c, batch)
            else:
                for xml in xml_records:
                    result = parse_single_record((xml,))
                    if result is not None:
                        parsed_records.append(result)
                        if len(parsed_records) >= batch_size:
                            batch = parsed_records
                            parsed_records = []
                            self._insert_batch_to_cursor(c, batch)

            if parsed_records:
                self._insert_batch_to_cursor(c, parsed_records)

        except Exception as e:
            print(f"  解析失败: {e}")
            conn.close()
            raise

        try:
            # 提交事务 + 双重WAL checkpoint，确保数据刷入主数据库文件
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            
            total = c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            conn.close()
            
            # 验证数据确实写入
            verify_conn = sqlite3.connect(self.db_path)
            verify_total = verify_conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            verify_conn.close()
            
            if verify_total != total:
                raise Exception(f"验证失败: 预期{total}条, 实际{verify_total}条")
            
            total_time = time.time() - start
            print(f"  数据库构建完成: {total}条, 总耗时{total_time:.2f}秒")
            return total
        except Exception as e:
            conn.close()
            raise

    @staticmethod
    def _insert_batch_to_cursor(cursor, batch):
        """批量插入数据（不含RawXML以节省空间）"""
        batch_no_xml = []
        for item in batch:
            item_copy = {k: v for k, v in item.items() if k != 'RawXML'}
            batch_no_xml.append(item_copy)
        cursor.executemany('''
            INSERT INTO events (
                record_id, event_id, version, level, level_text, task, opcode, keywords,
                time_created, time_created_raw, event_record_id,
                correlation_activity_id, correlation_related_activity_id,
                execution_process_id, execution_thread_id,
                provider, provider_guid, channel, computer, user_id, message, event_data
            )
            VALUES (
                :RecordID, :EventID, :Version, :Level, :LevelText, :Task, :Opcode, :Keywords,
                :TimeCreated, :TimeCreatedRaw, :EventRecordID,
                :CorrelationActivityID, :CorrelationRelatedActivityID,
                :ExecutionProcessID, :ExecutionThreadID,
                :Provider, :ProviderGUID, :Channel, :Computer, :UserID, :Message, :EventData
            )
        ''', batch_no_xml)

    def ensure_db(self, use_multiprocess: bool = True) -> int:
        """
        确保数据库是最新的，如果需要则构建
        返回: 事件数量
        """
        needs_rebuild = False
        
        if not os.path.exists(self.db_path):
            needs_rebuild = True
        else:
            try:
                # 清理可能残留的WAL/SHM文件
                for suffix in ['-wal', '-shm']:
                    path = self.db_path + suffix
                    if os.path.exists(path):
                        os.remove(path)
                
                conn = sqlite3.connect(self.db_path)
                columns = [row[1] for row in conn.execute("PRAGMA table_info(events)").fetchall()]
                total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                conn.close()
                
                if 'raw_xml' in columns:
                    needs_rebuild = True
                elif total == 0:
                    needs_rebuild = True
                elif evtx_needs_update(self.evtx_path, self.db_path):
                    needs_rebuild = True
            except Exception:
                needs_rebuild = True
        
        if needs_rebuild:
            # 先清理旧数据库和WAL/SHM文件
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
            for suffix in ['-wal', '-shm']:
                path = self.db_path + suffix
                if os.path.exists(path):
                    os.remove(path)
            return self._build_db(use_multiprocess)
        else:
            conn = sqlite3.connect(self.db_path)
            total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            conn.close()
            return total

    def query(self, page: int = 1, page_size: int = 200, levels: List[str] = None, time_range: int = None, time_from: str = None, time_to: str = None, sort_order: str = 'desc') -> Dict[str, Any]:
        """
        从数据库查询事件（分页，支持级别过滤、时间过滤、排序）
        """
        self.ensure_db()
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # 构建 WHERE 条件
        where_parts = []
        params = []

        # 级别过滤
        if levels:
            placeholders = ','.join(['?' for _ in levels])
            where_parts.append(f"level IN ({placeholders})")
            params.extend(levels)

        # 时间范围过滤
        if time_range is not None and time_range >= 0:
            from datetime import datetime, timedelta
            now = datetime.now()
            if time_range == 0:  # 今天
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                start_date = now - timedelta(days=time_range)
            start_str = start_date.strftime('%Y-%m-%d %H:%M:%S')
            where_parts.append("time_created >= ?")
            params.append(start_str)
        elif time_from or time_to:
            if time_from:
                where_parts.append("time_created >= ?")
                params.append(time_from)
            if time_to:
                where_parts.append("time_created <= ?")
                params.append(time_to)

        where_clause = " WHERE " + " AND ".join(where_parts) if where_parts else ""

        # 统计总数
        total = c.execute(f"SELECT COUNT(*) FROM events{where_clause}", params).fetchone()[0]
        offset = (page - 1) * page_size

        # 排序方向
        order_direction = "DESC" if sort_order.lower() == 'desc' else "ASC"

        # 查询数据
        rows = c.execute(
            f"SELECT * FROM events{where_clause} ORDER BY time_created {order_direction} LIMIT ? OFFSET ?",
            params + [page_size, offset]
        ).fetchall()

        events = []
        for row in rows:
            events.append({
                'RecordID': row['record_id'] or '',
                'EventID': row['event_id'] or '',
                'Version': row['version'] or '',
                'Level': row['level'] or '',
                'LevelText': row['level_text'] or '',
                'Task': row['task'] or '',
                'Opcode': row['opcode'] or '',
                'Keywords': row['keywords'] or '',
                'TimeCreated': row['time_created'] or '',
                'TimeCreatedRaw': row['time_created_raw'] or '',
                'EventRecordID': row['event_record_id'] or '',
                'CorrelationActivityID': row['correlation_activity_id'] or '',
                'CorrelationRelatedActivityID': row['correlation_related_activity_id'] or '',
                'ExecutionProcessID': row['execution_process_id'] or '',
                'ExecutionThreadID': row['execution_thread_id'] or '',
                'Provider': row['provider'] or '',
                'ProviderGUID': row['provider_guid'] or '',
                'Channel': row['channel'] or '',
                'Computer': row['computer'] or '',
                'UserID': row['user_id'] or '',
                'Message': row['message'] or '',
                'EventData': json.loads(row['event_data']) if row['event_data'] else {},
                'RawXML': ''
            })

        conn.close()
        return {
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size if total > 0 else 0,
            'events': events
        }

    def search(self, keyword: str, page: int = 1, page_size: int = 200, levels: List[str] = None, time_range: int = None, time_from: str = None, time_to: str = None, sort_order: str = 'desc') -> Dict[str, Any]:
        """搜索所有字段（System字段 + EventData JSON内容）"""
        self.ensure_db()
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        like = f'%{keyword}%'
        # 搜索所有System字段 + EventData JSON内容
        search_fields = [
            'record_id', 'event_id', 'version', 'level', 'level_text',
            'task', 'opcode', 'keywords', 'time_created', 'time_created_raw',
            'event_record_id', 'correlation_activity_id', 'correlation_related_activity_id',
            'execution_process_id', 'execution_thread_id',
            'provider', 'provider_guid', 'channel', 'computer', 'user_id', 'message', 'event_data'
        ]
        base_where = " WHERE " + " OR ".join([f"{f} LIKE ?" for f in search_fields])
        params = [like for _ in search_fields]
        
        # 级别过滤
        if levels:
            placeholders = ','.join(['?' for _ in levels])
            base_where += f" AND level IN ({placeholders})"
            params.extend(levels)

        # 时间范围过滤
        if time_range is not None and time_range >= 0:
            from datetime import datetime, timedelta
            now = datetime.now()
            if time_range == 0:  # 今天
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                start_date = now - timedelta(days=time_range)
            start_str = start_date.strftime('%Y-%m-%d %H:%M:%S')
            base_where += " AND time_created >= ?"
            params.append(start_str)
        elif time_from or time_to:
            if time_from:
                base_where += " AND time_created >= ?"
                params.append(time_from)
            if time_to:
                base_where += " AND time_created <= ?"
                params.append(time_to)

        total = c.execute(
            f"SELECT COUNT(*) FROM events {base_where}", params
        ).fetchone()[0]
        offset = (page - 1) * page_size

        # 排序方向
        order_direction = "DESC" if sort_order.lower() == 'desc' else "ASC"

        rows = c.execute(
            f"SELECT * FROM events {base_where} ORDER BY time_created {order_direction} LIMIT ? OFFSET ?",
            params + [page_size, offset]
        ).fetchall()

        events = []
        for row in rows:
            events.append({
                'RecordID': row['record_id'] or '',
                'EventID': row['event_id'] or '',
                'Version': row['version'] or '',
                'Level': row['level'] or '',
                'LevelText': row['level_text'] or '',
                'Task': row['task'] or '',
                'Opcode': row['opcode'] or '',
                'Keywords': row['keywords'] or '',
                'TimeCreated': row['time_created'] or '',
                'TimeCreatedRaw': row['time_created_raw'] or '',
                'EventRecordID': row['event_record_id'] or '',
                'CorrelationActivityID': row['correlation_activity_id'] or '',
                'CorrelationRelatedActivityID': row['correlation_related_activity_id'] or '',
                'ExecutionProcessID': row['execution_process_id'] or '',
                'ExecutionThreadID': row['execution_thread_id'] or '',
                'Provider': row['provider'] or '',
                'ProviderGUID': row['provider_guid'] or '',
                'Channel': row['channel'] or '',
                'Computer': row['computer'] or '',
                'UserID': row['user_id'] or '',
                'Message': row['message'] or '',
                'EventData': json.loads(row['event_data']) if row['event_data'] else {},
                'RawXML': ''
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
