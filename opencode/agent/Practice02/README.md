# Practice02 — 流式对话 Agent 与本地工具调用

本目录是一组渐进式练习脚本,演示如何在命令行对话中给大模型接入本地工具(function calling):

| 文件 | 说明 |
| --- | --- |
| `chat.py` | 第一版:基础流式多轮对话 |
| `chat2.py` | 新增 `getDate`、`isLeapYear` 两个演示工具 |
| `chat3.py` | 在 `chat2.py` 基础上新增 **10 个本地文件操作工具**,共 12 个工具 |
| `chat3_architecture.mmd` | `chat3.py` 代码架构图(Mermaid 纯文本,可用 mermaid.live / VS Code Mermaid 插件打开) |
| `config.ini` | 本地 API 配置(**不要提交仓库**) |

## 功能

- API Key / 接口地址 / 模型从本地 `config.ini` 读取,不硬编码
- 多轮循环对话,`stream=True` 流式逐字打印模型回复
- 完整的工具调用闭环:模型返回 `tool_calls` → 本地执行 → 以 `role=tool` 回写结果 → 继续对话(最多 `MAX_TOOL_ROUNDS = 10` 轮)
- 12 个内置工具(见下表),失败场景统一打印中文错误并以退出码 `1` 结束
- 兼容任何 OpenAI 风格的 `/v1/chat/completions` 接口

## 工具列表

### 演示工具

| 工具 | 参数 | 实现方式 |
| --- | --- | --- |
| `getDate` | 无 | `subprocess` 调用本地 `date` 命令(Windows 走 `cmd /u /c`) |
| `isLeapYear` | `year`(整数) | 纯 Python 计算闰年 |

### 本地文件操作工具(10 个)

全部用 Python 标准库(`pathlib` / `shutil` / `mimetypes`)实现,跨平台,不依赖 shell 命令:

| # | 工具 | 参数 | 说明 |
| --- | --- | --- | --- |
| 1 | `getToolsDirectory` | 无 | 返回脚本(`chat3.py`)所在目录的绝对路径 |
| 2 | `listDirectory` | `path` | 列出目录下所有文件和子目录,文件附带字节大小 |
| 3 | `getFileType` | `path` | 返回文件类型:文件/目录、扩展名、MIME 类型、大小 |
| 4 | `readFile` | `path` | 读取文件内容,**仅支持纯文本**;NUL 字节判定二进制并拒绝,超 20000 字符截断 |
| 5 | `createFile` | `directory`, `filename`, `content?` | 按目录+文件名创建新文件,**目录不存在时自动逐级创建** |
| 6 | `editFile` | `path`, `mode`, `content?`, `old_text?`, `new_text?` | 编辑纯文本文件:`write` 覆盖 / `append` 追加 / `replace` 查找替换 |
| 7 | `createDirectory` | `path` | 创建新目录(含上级目录),已存在不报错 |
| 8 | `deleteDirectory` | `path` | 删除目录及**全部内容(支持非空)**,`shutil.rmtree` 实现 |
| 9 | `deleteFile` | `path` | 删除文件,`Path.unlink` 实现 |
| 10 | `renameItem` | `old_path`, `new_path` | 重命名/移动文件或目录,可跨目录 |

### 安全防护

- `deleteDirectory` 拒绝删除磁盘根目录(`D:\` 等)与工具自身所在目录
- `readFile` / `editFile` 拒绝二进制文件,编码依次尝试 `utf-8` → 系统编码 → `gbk`
- 所有 `OSError` 在 `make_handler` 中统一捕获,返回中文错误文案而非堆栈

## 环境要求

- Python 3.8+
- 依赖:`requests`

```bash
pip install requests
```

## 配置

在本目录 `config.ini` 中填写:

```ini
; 本地配置,API Key 不要提交到仓库
[api]
key = sk-xxxxxxxx
base_url = https://api.openai.com/v1
model = gpt-4o-mini
```

同名环境变量可替代:`CHAT_API_KEY`、`CHAT_BASE_URL`、`CHAT_MODEL`。
取值优先级:`config.ini` > 环境变量 > 内置默认值(`key` 无默认值,缺失即报错)。

## 运行

```bash
python chat3.py
```

示例提示词:

```text
请输入提示词: 在当前目录创建 demo 目录,里面新建 hello.txt 写入你好,然后读出来给我看
```

执行过程中会打印 `[tool] 工具名 -> 结果` 形式的调用日志,模型据此继续作答。

## 架构

架构图见 [`chat3_architecture.mmd`](chat3_architecture.mmd)(Mermaid `flowchart TD` 纯文本):

```text
main
 ├─ load_config()          读取 config.ini / 环境变量
 ├─ read_prompt()          外层循环:输入提示词
 └─ 内层循环
     ├─ open_stream()      POST /chat/completions (stream=true, tools=TOOLS)
     ├─ iter_events()      解析 SSE: text 分片 → 流式打印
     │                     reasoning 分片 → 攒 reasoning_content 备回传
     │                     tool_calls → 按 index 聚合标准格式
     │                     {id, type:"function", function:{name, arguments}}
     ├─ dispatch_tool()    工具分发
     │   ├─ getDate → run_date_command (subprocess)
     │   ├─ isLeapYear → check_leap_year
     │   └─ FILE_TOOL_HANDLERS → make_handler(func)
     │         ├─ parse_arguments()      JSON 校验
     │         ├─ required/optional 参数校验
     │         └─ 10 个文件工具函数(共享 load_text_file / _guard_removable)
     └─ 回写 role=tool 结果,rounds > 10 则退出
```

## 实现要点

1. `TOOLS` 列表为 12 个工具定义 JSON Schema(名称、中文描述、参数类型),随每次请求一起发送
2. `make_handler(func, required, optional)` 是通用工具包装器:负责 JSON 解析、缺参校验、`OSError` 统一捕获,10 个文件工具各一行注册进 `FILE_TOOL_HANDLERS`
3. `editFile` 用 `mode` 参数在一次调用里支持三种编辑语义,`replace` 要求 `old_text` 必须存在于文件中,否则报错不写入
4. `createFile` 的 `mkdir(parents=True)` 同时满足"创建新目录"的需求;`renameItem` 对 `new_path` 的父目录同样自动创建
5. 流式解析、错误分类(401/403/404/429/5xx)、历史消息管理与 `chat2.py` 保持一致
6. **回传 assistant 消息使用标准 tool_calls 格式** `{id, type: "function", function: {name, arguments}}`;若像早期版本那样扁平回传 `{id, name, arguments}`,DeepSeek 等接口会报 `422 missing field 'type'`
7. 思考模式模型(如 `deepseek-flash`)的流式响应带 `reasoning_content`,`iter_events` 以 `("reasoning", 片段)` 产出并随 assistant 消息一并回传,否则下一轮报 `400 The reasoning_content ... must be passed back`

## 安全提示

- `config.ini` 含真实密钥,请勿提交到仓库或分享
- `deleteDirectory` / `deleteFile` / `write` 模式均不可恢复,建议只对临时/测试目录调用
- 工具无路径沙箱限制,模型可操作任意可写路径;仅在可信环境运行
