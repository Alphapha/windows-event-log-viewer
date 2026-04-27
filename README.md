# Windows事件日志查看器

一个基于Flask的Web应用，用于在浏览器中查看和分析Windows事件日志文件(.evtx)。

## 功能说明

- 📁 **文件浏览**：左侧显示evtx目录下所有EVTX日志文件
- 📊 **日志查看**：右侧以表格形式展示事件日志全部内容
- 🎯 **字段选择**：可自定义选择要显示的字段列
- 🎨 **级别标识**：事件级别以彩色标签区分（严重/错误/警告/信息/详细）
- 📈 **统计信息**：显示事件总数和加载时间

## 技术栈

- **后端**：Python 3 + Flask
- **解析库**：python-evtx（解析Windows EVTX格式日志）
- **前端**：原生HTML + CSS + JavaScript（无框架依赖）

## 安装步骤

### 1. 克隆项目

```bash
git clone <repository-url>
cd 1-Windows日志分析
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

依赖包说明：
- `flask==3.0.0`：Web框架
- `python-evtx==0.7.4`：EVTX文件解析库
- `python-dotenv==1.0.0`：环境变量管理

### 3. 配置环境变量（可选）

编辑 `.env` 文件：

```env
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=True
```

## 使用方法

### 1. 准备EVTX文件

将Windows事件日志文件(.evtx)放入 `evtx/` 目录下：

```
evtx/
├── Application.evtx
├── Security.evtx
└── System.evtx
```

### 2. 启动应用

```bash
python app.py
```

启动成功后，终端会显示：
```
* Running on http://127.0.0.1:5000
```

### 3. 访问Web界面

打开浏览器访问：`http://127.0.0.1:5000`

### 4. 查看日志

1. 在左侧文件列表中点击要查看的EVTX文件
2. 右侧会自动解析并展示所有事件记录
3. 在顶部工具栏勾选/取消字段，自定义显示内容

## 核心逻辑

### 项目结构

```
1-Windows日志分析/
├── app.py                 # Flask Web服务器
├── evtx_parser.py         # EVTX解析器
├── requirements.txt       # Python依赖
├── .env                   # 环境配置
├── templates/
│   └── index.html         # 前端页面
└── evtx/                  # EVT日志文件目录
    ├── Application.evtx
    ├── Security.evtx
    └── System.evtx
```

### API接口说明

#### 1. 获取文件列表
```
GET /api/files
```
响应示例：
```json
{
  "status": "success",
  "files": [
    {
      "filename": "Application.evtx",
      "filepath": "/path/to/Application.evtx",
      "size": 1234567
    }
  ]
}
```

#### 2. 获取事件数据
```
GET /api/events?filename=Application.evtx
```
响应示例：
```json
{
  "status": "success",
  "filename": "Application.evtx",
  "total": 100,
  "events": [
    {
      "RecordID": "1234",
      "EventID": "1001",
      "TimeCreated": "2024-01-01 12:00:00",
      "Level": "信息",
      "Provider": "Application",
      "Message": "..."
    }
  ]
}
```

#### 3. 获取可用字段
```
GET /api/fields
```
响应示例：
```json
{
  "status": "success",
  "fields": [
    {"id": "RecordID", "name": "记录ID", "default": true},
    {"id": "EventID", "name": "事件ID", "default": true}
  ]
}
```

### 解析字段说明

| 字段 | 说明 | 默认显示 |
|------|------|----------|
| RecordID | 事件记录ID | ✓ |
| EventID | 事件ID | ✓ |
| TimeCreated | 创建时间 | ✓ |
| Level | 事件级别（严重/错误/警告/信息/详细） | ✓ |
| Provider | 事件提供程序 | ✓ |
| Channel | 日志通道 | ✗ |
| Computer | 计算机名 | ✗ |
| UserID | 用户ID | ✗ |
| Message | 事件消息 | ✓ |
| EventData | 事件详细数据（JSON格式） | ✗ |
| RawXML | 原始XML数据 | ✗ |

### 事件级别映射

| 代码 | 级别 | 颜色 |
|------|------|------|
| 1 | 严重 | 红色 |
| 2 | 错误 | 橙色 |
| 3 | 警告 | 黄色 |
| 4 | 信息 | 绿色 |
| 5 | 详细 | 蓝色 |

## 注意事项

1. **跨平台限制**：`python-evtx`库可在Mac/Linux上读取Windows EVTX文件，但文件必须来自Windows系统
2. **大文件性能**：大型EVTX文件（>100MB）解析可能需要较长时间，请耐心等待
3. **内存占用**：解析时会将所有事件加载到内存，建议在8GB以上内存的机器上运行
4. **编码问题**：部分事件日志可能包含特殊字符，已做异常处理，但个别记录可能跳过
5. **安全提示**：不要在公共网络暴露此服务，建议仅在本机访问（127.0.0.1）

## 常见问题

### Q1: 安装python-evtx失败

**问题**：`pip install python-evtx` 报错

**解决方法**：
```bash
# 使用国内镜像源
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple python-evtx

# 或者先升级pip
pip install --upgrade pip
pip install python-evtx
```

### Q2: 打开网页后显示"未找到EVTX文件"

**问题**：左侧文件列表为空

**解决方法**：
1. 确认 `evtx/` 目录存在且包含 .evtx 文件
2. 检查文件路径是否正确（相对于app.py的位置）
3. 确认文件扩展名为 `.evtx`（区分大小写）

### Q3: 解析事件时部分记录丢失

**问题**：显示的事件数量少于预期

**解决方法**：
- Windows事件日志可能存在损坏的记录，解析器会自动跳过无法解析的记录
- 查看终端输出，确认是否有 `解析事件时出错` 的警告信息

### Q4: 如何导出事件数据？

**问题**：需要将数据导出为CSV或Excel

**解决方法**：
当前版本暂不支持导出功能，可通过以下方式实现：
1. 浏览器开发者工具中复制表格数据
2. 或使用脚本调用API：
```python
import requests
response = requests.get('http://127.0.0.1:5000/api/events?filename=Application.evtx')
data = response.json()
# 使用pandas导出为CSV
import pandas as pd
df = pd.DataFrame(data['events'])
df.to_csv('events.csv', index=False)
```

### Q5: 如何修改端口？

**问题**：5000端口被占用

**解决方法**：
编辑 `.env` 文件，修改端口：
```env
FLASK_PORT=8080
```
然后重启应用。

## 许可证

MIT License

## 更新日志

### v1.0.0 (2024-04-27)
- ✨ 初始版本发布
- ✨ 支持EVTX文件解析和Web展示
- ✨ 字段选择功能
- ✨ 事件级别彩色标识
