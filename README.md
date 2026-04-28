# Windows事件日志查看器

一个基于Flask的Web应用，用于在浏览器中查看和分析Windows事件日志文件(.evtx)。

## 功能说明

- 📁 **文件浏览**：左侧显示evtx目录下所有EVTX日志文件
- 📂 **分类筛选**：按日志类型（安全/系统/应用程序等）分类显示，支持下拉筛选
- 📊 **日志查看**：右侧以表格形式展示事件日志全部内容
- 🎯 **字段选择**：可自定义选择要显示的字段列
- 🎨 **级别标识**：事件级别以彩色标签区分（严重/错误/警告/信息/详细）
- 🔍 **级别过滤**：顶部工具栏提供级别多选按钮，支持多级别同时筛选
- ⏱️ **时间过滤**：支持时间范围筛选（今天/近3天/近7天/近1月/近3月/自定义日期范围）
- 🔃 **时间排序**：支持按创建时间正序/倒序排列，默认倒序（时间近的优先）
- 📈 **统计信息**：显示事件总数、查询耗时和缓存状态
- ⚡ **缓存加速**：首次解析后自动缓存，二次访问秒级加载
- 🔄 **手动重建**：支持强制重新构建数据库
- 🚀 **多进程解析**：利用多核CPU加速首次解析

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

### 2. 上传EVTX文件

点击左侧边栏的「📤 上传EVTX日志」按钮，选择要上传的 .evtx 文件：

- **自动MD5去重**：上传前自动计算MD5，如果文件已存在则提示重复
- **文件名冲突处理**：如果同名文件存在，自动添加 `_1`、`_2` 等后缀
- **大小限制**：单个文件最大支持 500MB
- **格式限制**：仅支持 `.evtx` 格式文件
- **上传后自动刷新**：上传成功后左侧文件列表自动更新

上传后点击新文件即可开始查看。

### 3. 启动应用

```bash
python app.py
```

启动成功后，终端会显示：
```
* Running on http://127.0.0.1:5000
```

### 4. 访问Web界面

打开浏览器访问：`http://127.0.0.1:5000`

### 4. 查看日志

1. 使用顶部分类下拉列表筛选日志类型（可选）
2. 在左侧文件列表中点击要查看的EVTX文件
3. 右侧会自动解析并展示所有事件记录（首次可能较慢，请耐心等待）
4. 在顶部工具栏勾选/取消字段，自定义显示内容
5. 使用级别过滤按钮筛选特定级别的事件（支持多选）
6. 使用时间过滤按钮筛选特定时间范围内的事件
7. 点击排序按钮切换时间正序/倒序排列
8. 点击「🔄 重建」按钮可强制重新构建数据库（如果数据异常或损坏时使用）

#### 上传API

```
POST /api/upload
Content-Type: multipart/form-data

Form fields:
  file: .evtx file

Response (success):
{
  "status": "success",
  "message": "上传成功: xxx.evtx",
  "filename": "xxx.evtx",
  "md5": "abc123...",
  "size": 123456
}

Response (duplicate):
{
  "status": "duplicate",
  "message": "文件已存在: xxx.evtx",
  "md5": "abc123...",
  "existing_filename": "xxx.evtx"
}
```

## SQLite 数据库机制

应用采用 **SQLite 预处理**策略，实现极速查询体验（类似 Windows 事件查看器）：

- **首次打开**：自动解析 EVTX 文件并构建 SQLite 数据库（多进程并发加速）
- **数据库位置**：`evtx/db/` 目录，每个 .evtx 对应一个 .db 文件
- **二次访问**：直接从 SQLite 查询，**毫秒级响应**（与 Windows 事件查看器一样快）
- **自动检测**：当 EVTX 文件被更新时，自动重新构建数据库
- **分页查询**：每页 200 条，快速翻页不卡顿
- **搜索功能**：支持按事件ID/提供程序/消息关键词搜索
- **重建索引**：点击「重建」按钮可手动重建数据库
- **空间优化**：不存储原始 XML，数据库大小约为 EVTX 文件的 1-3%
- **自动重建**：检测到旧数据库（包含 raw_xml 列）或空数据库时，自动重建
- **级别过滤**：支持按严重/错误/警告/信息/详细级别多选筛选
- **时间过滤**：支持按时间范围筛选（今天/近N天/自定义日期范围）
- **时间排序**：支持按创建时间正序/倒序排列
- **WAL 模式优化**：采用 SQLite WAL 模式并自动 checkpoint，确保数据一致性
- **多连接安全**：解析和查询使用独立连接，避免并发冲突
- **双重验证**：构建完成后自动验证数据完整性

### 性能对比

| 指标 | JSON 缓存 | SQLite 数据库 |
|------|----------|--------------|
| 首次加载 | 解析 + 序列化 | 解析 + 建库（多进程） |
| 翻页查询 | 加载全部到内存 | **毫秒级 SQL 查询** |
| 内存占用 | 全部事件在内存 | **仅当前页在内存** |
| 搜索 | 需遍历全部 | **索引加速搜索** |
| 数据库大小 | 约等于 EVTX | **约 EVTX 的 1-3%** |

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
GET /api/events?filename=Application.evtx&page=1&page_size=200
GET /api/events?filename=Application.evtx&levels=错误,警告  # 按级别过滤（多选）
GET /api/events?filename=Application.evtx&time_range=7  # 近7天
GET /api/events?filename=Application.evtx&time_from=2024-01-01&time_to=2024-01-31  # 自定义时间范围
GET /api/events?filename=Application.evtx&sort_order=desc  # 倒序（默认）
GET /api/events?filename=Application.evtx&sort_order=asc  # 正序
```

参数说明：
- `filename`: EVTX文件名（必填）
- `page`: 页码，默认1
- `page_size`: 每页条数，默认200
- `levels`: 级别过滤，逗号分隔（如：错误,警告,信息），不传表示全部级别
- `time_range`: 时间范围（天数），0=今天，3=近3天，7=近7天，30=近1月，90=近3月
- `time_from`: 自定义起始时间（格式：YYYY-MM-DD HH:MM:SS），与time_range互斥
- `time_to`: 自定义结束时间（格式：YYYY-MM-DD HH:MM:SS），与time_from配合使用
- `sort_order`: 排序方式，desc=倒序（时间近的优先，默认），asc=正序

响应示例：
```json
{
  "status": "success",
  "filename": "Application.evtx",
  "total": 5000,
  "page": 1,
  "page_size": 200,
  "total_pages": 25,
  "query_time": 0.0089,
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

### 解析字段说明（22个EVTX System字段）

| 字段 | 中文名 | 说明 | 默认显示 |
|------|--------|------|----------|
| RecordID | 记录ID | 事件记录编号 | ✓ |
| EventID | 事件ID | Windows事件ID | ✓ |
| Version | 版本 | 事件版本 | ✗ |
| Level | 级别 | 事件级别（严重/错误/警告/信息/详细） | ✓ |
| Task | 任务 | 事件任务类别 | ✗ |
| Opcode | 操作码 | 事件操作码 | ✗ |
| Keywords | 关键字 | 事件关键字掩码 | ✗ |
| TimeCreated | 创建时间 | 格式化后的事件时间（YYYY-MM-DD HH:MM:SS） | ✓ |
| TimeCreatedRaw | 原始时间 | ISO 8601格式原始时间 | ✗ |
| EventRecordID | 事件记录ID | 唯一记录标识符 | ✗ |
| CorrelationActivityID | 关联活动ID | 活动追踪ID | ✗ |
| CorrelationRelatedActivityID | 关联相关活动ID | 相关活动追踪ID | ✗ |
| ExecutionProcessID | 进程ID | 生成事件的进程ID | ✗ |
| ExecutionThreadID | 线程ID | 生成事件的线程ID | ✗ |
| Provider | 提供程序 | 事件提供程序名称 | ✓ |
| ProviderGUID | 提供程序GUID | 提供程序唯一标识符 | ✗ |
| Channel | 通道 | 日志通道（Security/System/Application等） | ✓ |
| Computer | 计算机 | 生成事件的计算机名 | ✓ |
| UserID | 用户ID | 关联用户SID | ✗ |
| Message | 消息 | 事件描述消息 | ✓ |
| EventData | 事件数据 | 事件详细数据（JSON格式） | ✗ |
| RawXML | 原始XML | 完整原始XML数据 | ✗ |

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
# 删除数据库目录
rm -rf evtx/db/

# 或者在网页中点击「🔄 重建」按钮强制重新构建数据库
```

### Q7: 重建后没有数据怎么办？

**问题**：点击「重建」按钮后，表格显示"没有匹配的事件"

**解决方法**：
1. 查看终端输出，确认解析是否完成（应显示"数据库构建完成: XXXX条"）
2. 检查 `evtx/db/` 目录下是否生成了对应的 `.db` 文件
3. 如果仍然没有数据，尝试：
   ```bash
   rm -rf evtx/db/
   python app.py
   ```
   然后重新点击文件触发解析
4. 数据库采用 WAL 模式，重建后会自动执行 checkpoint 确保数据写入
5. 如果问题持续，检查 EVTX 文件是否损坏

### Q8: 如何使用级别过滤功能？

**问题**：只想查看错误或警告级别的事件

**解决方法**：
1. 在顶部工具栏找到级别过滤按钮区域
2. 点击「全部」按钮取消全选，然后点击要筛选的级别按钮（如「错误」「警告」）
3. 支持多选，可同时选择多个级别
4. 再次点击「全部」按钮恢复显示所有事件
5. 级别过滤同样适用于搜索功能

### Q9: 如何使用时间过滤功能？

**问题**：只想查看最近几天的事件，或指定时间范围内的事件

**解决方法**：
1. 在顶部工具栏找到时间过滤按钮区域
2. 点击预设按钮快速筛选：
   - 「今天」：显示今天00:00至今的事件
   - 「近3天」：显示近3天的事件
   - 「近7天」：显示近7天的事件
   - 「近1月」：显示近30天的事件
   - 「近3月」：显示近90天的事件
3. 点击「指定」按钮，会出现日期时间选择器
4. 选择起始时间和结束时间（精确到分钟）
5. 时间过滤同样适用于搜索功能

### Q10: 如何切换时间排序方式？

**问题**：想按时间从早到晚或从晚到早查看事件

**解决方法**：
1. 在顶部工具栏找到排序按钮区域
2. 点击「↓ 倒序」按钮：时间近的优先（默认）
3. 点击「↑ 正序」按钮：时间早的优先
4. 排序方式在切换文件后会重置为默认倒序

### Q11: 解析速度太慢怎么办？

**问题**：首次解析一个大型EVTX文件需要很长时间

**解决方法**：
1. 这是正常现象，大型文件（如50MB+）可能需要数分钟
2. 应用会自动使用多进程并发解析，已是最优速度
3. 解析完成后会存入SQLite数据库，后续查询都是毫秒级
4. 数据库文件保存在 `evtx/db/` 目录，可以重复使用
5. 如需加快首次解析，可考虑将大文件分割为多个小文件

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

### v3.5.0 (2026-04-27)
- ️ **文件管理**：新增文件删除和归档操作，鼠标悬停文件显示操作按钮
- 📦 **归档功能**：归档文件移动到 `evtx_archive/` 目录，带时间戳命名，可一键恢复
-  **全局同步**：基于版本号的长轮询机制，文件变更（删除/归档/恢复/上传）自动全局刷新
-  **归档面板**：左侧边栏底部新增归档文件面板，可展开查看和恢复
- 📖 **文档完善**：新增文件管理使用说明和更新日志

### v3.4.0 (2026-04-27)
- 📤 **上传功能**：新增EVTX文件上传按钮，支持从浏览器直接上传日志文件
-  **MD5去重**：上传时自动计算MD5并检查重复，避免重复上传
- 📊 **查询时间显示**：修复底部状态栏查询时间显示undefined的问题
- 📝 **API文档**：新增上传API接口说明
- 📖 **文档完善**：更新使用方法和更新日志

### v3.3.0 (2026-04-27)
- 📊 **字段全面扩展**：解析字段从11个扩展到22个EVTX System字段
- 🆕 **新增字段**：Version/Task/Opcode/Keywords/TimeCreatedRaw/EventRecordID/CorrelationActivityID/ExecutionProcessID/ExecutionThreadID/ProviderGUID等
- 🎯 **字段可选**：所有EVTX System字段均可作为按钮点选显示/隐藏
- 🎨 **按钮样式修复**：修复「全部」级别按钮激活时白底白字问题
- 📖 **文档完善**：更新字段说明表格，列出全部22个字段

### v3.2.0 (2026-04-27)
- 🎯 **级别多选按钮**：级别过滤改为点选按钮形式，支持多选
- ⏱️ **时间过滤功能**：新增今天/近3天/近7天/近1月/近3月/自定义日期范围过滤
- 🔃 **时间排序功能**：支持按创建时间正序/倒序排列，默认倒序
- 🎨 **界面优化**：工具栏分行布局，筛选器更紧凑美观
- 📖 **文档完善**：新增时间过滤和排序使用说明

### v3.1.0 (2026-04-27)
- 🔄 **重建可靠性提升**：修复WAL模式下的数据可见性问题，确保重建后立即可见
- 🎯 **级别过滤增强**：支持在事件列表和搜索中按级别筛选
- ✅ **数据验证机制**：构建完成后自动验证数据完整性
- ️ **异常处理优化**：解析失败时自动清理残留文件
- 📖 **文档完善**：新增FAQ和级别过滤使用说明

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
