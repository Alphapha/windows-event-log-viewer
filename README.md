# Windows事件日志查看器

一个基于Flask的Web应用，用于在浏览器中查看和分析Windows事件日志文件(.evtx)。

## 功能说明

- 📁 **文件浏览**：左侧显示evtx目录下所有EVTX日志文件
- 📂 **分类筛选**：按日志类型（安全/系统/应用程序等）分类显示，支持下拉筛选
- 📊 **日志查看**：右侧以表格形式展示事件日志全部内容
- 🎯 **字段选择**：可自定义选择要显示的字段列
- 🎨 **级别标识**：事件级别以彩色标签区分（严重/错误/警告/信息/详细）
- 📈 **统计信息**：显示事件总数、解析耗时和缓存状态
- ⚡ **缓存加速**：首次解析后自动缓存，二次访问秒级加载
- 🔄 **手动刷新**：支持强制重新解析（跳过缓存）

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

1. 使用顶部分类下拉列表筛选日志类型（可选）
2. 在左侧文件列表中点击要查看的EVTX文件
3. 右侧会自动解析并展示所有事件记录
4. 在顶部工具栏勾选/取消字段，自定义显示内容
5. 点击「🔄 刷新」按钮可强制重新解析（跳过缓存）

## 缓存机制

应用采用智能缓存策略提升性能：

- **首次解析**：完整解析EVTX文件，可能需要几秒到几分钟（取决于文件大小）
- **缓存存储**：解析结果保存为JSON文件在 `evtx/cache/` 目录
- **二次访问**：直接从缓存加载，通常 <0.1 秒
- **自动更新**：当EVTX文件修改时间或大小变化时，自动重新解析
- **手动刷新**：点击刷新按钮可跳过缓存强制重新解析

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

#### 1. 获取文件列表（按类别分组）
```
GET /api/files
```
响应示例：
```json
{
  "status": "success",
  "categories": {
    "系统日志": [
      {
        "filename": "System.evtx",
        "filepath": "/path/to/System.evtx",
        "size": 1234567,
        "category": "系统日志"
      }
    ],
    "安全日志": [
      {
        "filename": "Security.evtx",
        "filepath": "/path/to/Security.evtx",
        "size": 2345678,
        "category": "安全日志"
      }
    ]
  }
}
```

#### 2. 获取事件数据
```
GET /api/events?filename=Application.evtx
GET /api/events?filename=Application.evtx&refresh=true  # 强制刷新，跳过缓存
```
响应示例：
```json
{
  "status": "success",
  "filename": "Application.evtx",
  "total": 100,
  "parse_time": 0.05,
  "from_cache": true,
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

响应字段说明：
- `parse_time`: 解析耗时（秒）
- `from_cache`: 是否从缓存加载（true表示秒开）

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

### 日志分类说明

| 分类 | 说明 | 常见文件 |
|------|------|----------|
| 安全日志 | Windows安全审计事件 | Security.evtx |
| 系统日志 | Windows系统组件事件 | System.evtx |
| 应用程序日志 | 应用程序相关事件 | Application.evtx |
| Setup日志 | Windows安装事件 | Setup.evtx |
| 其他日志 | 未归类的日志文件 | 其他*.evtx |

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

### Q3: 第一次解析很慢怎么办？

**问题**：首次打开EVTX文件需要很长时间

**解决方法**：
- 这是正常现象，首次解析需要将二进制EVTX转换为结构化数据
- 解析完成后会自动缓存，第二次打开即秒级加载
- 缓存文件存储在 `evtx/cache/` 目录
- 缓存根据文件修改时间自动失效，确保数据最新

### Q4: 如何清空缓存？

**问题**：需要清空缓存重新解析所有文件

**解决方法**：
```bash
# 删除缓存目录
rm -rf evtx/cache/

# 或者在网页中点击「🔄 刷新」按钮强制重新解析
```

### Q5: 解析事件时部分记录丢失

**问题**：显示的事件数量少于预期

**解决方法**：
- Windows事件日志可能存在损坏的记录，解析器会自动跳过无法解析的记录
- 查看终端输出，确认是否有 `解析事件时出错` 的警告信息

### Q6: 如何导出事件数据？

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

### Q6: 如何修改端口？

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

### v3.0.0 (2026-04-27)
- 🚀 **SQLite 预处理机制**：首次解析后存入 SQLite，后续查询毫秒级响应
- ⚡ **多进程并发解析**：利用多核 CPU 加速首次解析速度
- 🔍 **新增搜索功能**：支持按事件ID/提供程序/消息搜索
- 📄 **分页展示**：每页 200 条，快速翻页不卡顿
- 🔄 **重建数据库**：支持手动重建索引
- 📊 **查询时间显示**：底部状态栏显示查询耗时
- 🎨 **界面优化**：更紧凑的布局和配色

### v2.0.0 (2024-04-27)
- ✨ 新增日志分类功能（安全/系统/应用程序等）
- ✨ 新增左侧分类筛选下拉列表
- ⚡ 新增缓存机制，二次访问秒级加载
- 🔄 新增手动刷新按钮（跳过缓存）
- 📊 显示解析耗时和缓存状态
- 📝 优化README文档

### v1.0.0 (2024-04-27)
- ✨ 初始版本发布
- ✨ 支持EVTX文件解析和Web展示
- ✨ 字段选择功能
- ✨ 事件级别彩色标识
