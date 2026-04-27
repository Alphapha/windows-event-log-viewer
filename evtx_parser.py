"""
EVTX日志解析模块
用于解析Windows事件日志文件(.evtx)并提取日志数据
"""
import xml.etree.ElementTree as ET
from Evtx.Evtx import FileHeader
from datetime import datetime
from typing import List, Dict, Any
import os


class EvtxParser:
    """EVTX文件解析器"""

    def __init__(self, evtx_path: str):
        """
        初始化解析器
        
        Args:
            evtx_path: EVTX文件路径
        """
        self.evtx_path = evtx_path
        self.events = []
        
    def parse(self) -> List[Dict[str, Any]]:
        """
        解析EVTX文件,提取所有事件记录
        
        Returns:
            事件列表,每个事件为一个字典
        """
        self.events = []
        
        try:
            with open(self.evtx_path, 'rb') as f:
                buf = f.read()
                header = FileHeader(buf, 0)
                
                for chunk in header.chunks():
                    for record in chunk.records():
                        try:
                            xml_data = record.xml()
                            event_data = self._parse_xml(xml_data)
                            if event_data:
                                self.events.append(event_data)
                        except Exception as e:
                            print(f"解析事件时出错: {e}")
                            continue
        except Exception as e:
            print(f"打开文件 {self.evtx_path} 时出错: {e}")
            
        return self.events
    
    def _parse_xml(self, xml_string: str) -> Dict[str, Any]:
        """
        解析XML格式的事件数据
        
        Args:
            xml_string: XML格式的事件数据
            
        Returns:
            事件数据字典
        """
        try:
            root = ET.fromstring(xml_string)
            
            event_data = {
                'RecordID': self._get_record_id(root),
                'EventID': self._get_event_id(root),
                'TimeCreated': self._get_time_created(root),
                'Level': self._get_level(root),
                'Provider': self._get_provider(root),
                'Channel': self._get_channel(root),
                'Computer': self._get_computer(root),
                'UserID': self._get_user_id(root),
                'Message': self._get_message(root),
                'EventData': self._get_event_data(root),
                'RawXML': xml_string
            }
            
            return event_data
            
        except ET.ParseError as e:
            print(f"XML解析错误: {e}")
            return None
    
    def _get_record_id(self, root: ET.Element) -> str:
        """获取记录ID"""
        try:
            system = root.find('.//{http://schemas.microsoft.com/win/2004/08/events/event}System')
            if system is not None:
                record_id = system.find('{http://schemas.microsoft.com/win/2004/08/events/event}EventRecordID')
                if record_id is not None:
                    return record_id.text
        except:
            pass
        return ''
    
    def _get_event_id(self, root: ET.Element) -> str:
        """获取事件ID"""
        try:
            system = root.find('.//{http://schemas.microsoft.com/win/2004/08/events/event}System')
            if system is not None:
                event_id = system.find('{http://schemas.microsoft.com/win/2004/08/events/event}EventID')
                if event_id is not None:
                    return event_id.text
        except:
            pass
        return ''
    
    def _get_time_created(self, root: ET.Element) -> str:
        """获取创建时间"""
        try:
            system = root.find('.//{http://schemas.microsoft.com/win/2004/08/events/event}System')
            if system is not None:
                time_created = system.find('{http://schemas.microsoft.com/win/2004/08/events/event}TimeCreated')
                if time_created is not None:
                    utc_time = time_created.get('SystemTime')
                    if utc_time:
                        dt = datetime.fromisoformat(utc_time.replace('Z', '+00:00'))
                        return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            pass
        return ''
    
    def _get_level(self, root: ET.Element) -> str:
        """获取事件级别"""
        try:
            level_map = {
                '1': '严重',
                '2': '错误',
                '3': '警告',
                '4': '信息',
                '5': '详细'
            }
            system = root.find('.//{http://schemas.microsoft.com/win/2004/08/events/event}System')
            if system is not None:
                level = system.find('{http://schemas.microsoft.com/win/2004/08/events/event}Level')
                if level is not None:
                    return level_map.get(level.text, level.text)
        except:
            pass
        return ''
    
    def _get_provider(self, root: ET.Element) -> str:
        """获取提供程序"""
        try:
            system = root.find('.//{http://schemas.microsoft.com/win/2004/08/events/event}System')
            if system is not None:
                provider = system.find('{http://schemas.microsoft.com/win/2004/08/events/event}Provider')
                if provider is not None:
                    return provider.get('Name', '')
        except:
            pass
        return ''
    
    def _get_channel(self, root: ET.Element) -> str:
        """获取通道"""
        try:
            system = root.find('.//{http://schemas.microsoft.com/win/2004/08/events/event}System')
            if system is not None:
                channel = system.find('{http://schemas.microsoft.com/win/2004/08/events/event}Channel')
                if channel is not None:
                    return channel.text
        except:
            pass
        return ''
    
    def _get_computer(self, root: ET.Element) -> str:
        """获取计算机名"""
        try:
            system = root.find('.//{http://schemas.microsoft.com/win/2004/08/events/event}System')
            if system is not None:
                computer = system.find('{http://schemas.microsoft.com/win/2004/08/events/event}Computer')
                if computer is not None:
                    return computer.text
        except:
            pass
        return ''
    
    def _get_user_id(self, root: ET.Element) -> str:
        """获取用户ID"""
        try:
            system = root.find('.//{http://schemas.microsoft.com/win/2004/08/events/event}System')
            if system is not None:
                security = system.find('{http://schemas.microsoft.com/win/2004/08/events/event}Security')
                if security is not None:
                    return security.get('UserID', '')
        except:
            pass
        return ''
    
    def _get_message(self, root: ET.Element) -> str:
        """获取事件消息"""
        try:
            system = root.find('.//{http://schemas.microsoft.com/win/2004/08/events/event}System')
            if system is not None:
                message = system.find('{http://schemas.microsoft.com/win/2004/08/events/event}Message')
                if message is not None:
                    return message.text
        except:
            pass
        return ''
    
    def _get_event_data(self, root: ET.Element) -> Dict[str, str]:
        """获取事件详细数据"""
        event_data = {}
        try:
            event_data_elem = root.find('.//{http://schemas.microsoft.com/win/2004/08/events/event}EventData')
            if event_data_elem is not None:
                for data in event_data_elem.findall('{http://schemas.microsoft.com/win/2004/08/events/event}Data'):
                    name = data.get('Name', '')
                    value = data.text or ''
                    if name:
                        event_data[name] = value
                    else:
                        event_data[f'Data_{len(event_data)}'] = value
        except:
            pass
        return event_data


def get_evtx_files(directory: str) -> List[Dict[str, str]]:
    """
    获取指定目录下的所有EVTX文件
    
    Args:
        directory: 目录路径
        
    Returns:
        文件信息列表
    """
    evtx_files = []
    
    if not os.path.exists(directory):
        return evtx_files
    
    for filename in os.listdir(directory):
        if filename.endswith('.evtx'):
            filepath = os.path.join(directory, filename)
            evtx_files.append({
                'filename': filename,
                'filepath': filepath,
                'size': os.path.getsize(filepath)
            })
    
    return sorted(evtx_files, key=lambda x: x['filename'])
