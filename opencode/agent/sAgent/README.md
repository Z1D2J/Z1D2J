# sAgent

流式智能助手:业务核心(core)与界面(tui)完全分层,通过事件契约通信。
由 `agent/Practice02/chat3.py` 重构而来,继承其全部修复:
标准格式 `tool_calls` 回传、`reasoning_content` 思考内容回传。

## 运行

```powershell
python main.py            # 默认 TUI 界面(Textual)
python main.py --ui web   # 预留后端,尚未实现
```

依赖: `pip install -r requirements.txt`(textual, requests;Python 3.14)

配置: 默认读取**当前工作目录**的 `config.ini`,也可用环境变量 `SAGENT_CONFIG`
指定路径。文件不存在时会自动生成一份带 mock 值的完整配置,并在 TUI 中弹窗提示;
修改 `[api]` 的 `key / base_url / model` 和 `[search]` 的搜索 Key 后重启即可。
未填写的参数使用内置默认值,`CHAT_API_KEY` 等环境变量仍可作为兜底。

## 斜杠命令

在输入框中输入 `/` 会弹出补全面板: `↑/↓` 或 `Tab` 选择,`Enter` 执行,`Esc` 关闭。

| 命令 | 作用 |
| --- | --- |
| `/new` | 保存当前会话并开启新会话 |
| `/resume` | 打开会话列表,恢复历史会话(↑/↓ 选择, Enter 确认, Esc 取消) |
| `/save` | 立即保存当前会话 |
| `/compact` | 压缩上下文并归档原始记录 |
| `/status` | 查看会话、上下文与 MCP 状态 |
| `/mcp` | 查看 MCP 服务器与工具 |
| `/clear` | 清空屏幕显示(不删除历史) |
| `/help` | 显示全部命令 |
| `/quit` | 保存并退出 |

快捷键: `Ctrl+R` 新会话、`Ctrl+L` 清屏、`Ctrl+T` 折叠思考面板、`Ctrl+Q` 退出。

## 架构

```
main.py ──> tui/ (L4 表现层, Textual)
              │ 只依赖: core.Agent 的 run_turn/reset + core.events 契约
              ▼
           core/ (L1-L3, UI 无关, 不 import tui)
```

```
core/
├── config.py        L1 配置加载 (Settings, load_config)
├── errors.py        L1 错误类型 (ConfigError, AgentError)
├── events.py        L3 事件契约 (UI 唯一通信协议)
├── agent.py         L3 编排 (多轮工具往返, 事件推送, 历史维护, 上下文压缩)
├── context.py       L2 上下文预算 / JSONL 归档 / recallContext 检索实现
├── session.py       L2 会话持久化 (.agents/sessions/*.jsonl)
├── skills.py        L2 Skill 发现/元数据/按需加载 (SkillCatalog)
├── llm/
│   ├── client.py    L1 流式 HTTP 客户端 (错误翻译成中文文案)
│   └── (SSE 解析内置)
└── tools/
    ├── base.py      L2 注册框架 (ToolSpec / ToolRegistry / make_handler)
    ├── builtin.py   L2 getDate, isLeapYear
    ├── file_ops.py  L2 文件工具 10 个
    ├── office_cli.py L2 officeCli (调用 OfficeCli 生成/编辑 pptx/docx/xlsx)
    ├── run_cli.py   L2 RunCli (subprocess 列表形式执行本地命令)
    ├── web_fetch.py L2 fetchWeb (curl + trafilatura 网页正文转 Markdown)
    ├── web_search.py L2 searchWeb (百度千帆 AI 搜索, Bearer 鉴权)
    ├── recall.py    L2 recallContext (检索 .agents/context/ 归档)
    └── skill.py     L2 loadSkill / createSkill (按需读取或创建 Skill)
```

### 上下文压缩与历史检索

TUI 底部状态栏持续显示 `上下文 12.3k / 128k(默认) (9.6%)`。
上下文使用量包含 System Prompt、用户消息、对话历史和工具消息；
优先使用模型 API 返回的 `usage`，接口不提供时按字符估算。窗口大小可由
`config.ini` 的 `context_window`(如 `128k`)指定，未配置且无法识别模型时默认 128k。

- 达到上下文窗口 **60%** 时，界面显示警告并暂停接受新的普通提示词。
- 输入 `/compact` 手动压缩。压缩期间不允许执行其他工具，也不能继续原任务。
- 压缩前先把完整原始上下文写入 `.agents/context/<编号>.jsonl`(编号形如
  `20261022-153000`)，保存成功后才调用 LLM 生成约 5,000 Tokens 的 Markdown 摘要。
- 压缩完成后保留 System Prompt 与工具定义，用摘要替换历史，并弹出左右两栏对照面板
  (左: 压缩前原文，右: 压缩后结果，可滚动，可关闭)。
- 摘要末尾附带归档编号说明。LLM 可调用 `recallContext(id?, text)` 在指定或全部归档中
  做本地全文关键词检索，返回片段、归档编号和消息位置，结果长度受限。
- 压缩后保留所有前导 `system` 消息(主 System Prompt、AGENTS.md、Skills 说明),
  再放入摘要和新的 user/assistant 占位消息。

### 会话持久化

每个会话保存为 `.agents/sessions/<YYYYMMDD-HHMMSS>.jsonl`:
首行是 meta(id/created_at/updated_at/title),后续每行一条 message 事件,原样保存
role/content/tool_calls/tool_call_id/reasoning_content。保存使用临时文件 + 原子替换。

- 每轮成功结束后按 `[session] auto_save` 自动保存;`/save` 可立即保存。
- `/new` 会先保存旧会话,再切换到新编号;`/quit` 退出前也会保存。
- `/resume` 读取会话列表并恢复历史,恢复后可直接继续对话。
- 会话编号冲突时追加 `-1`、`-2` 等后缀。

### AGENTS.md 项目上下文

启动/新建/恢复会话时,若当前目录存在 `AGENTS.md`,会把它作为一条独立的 `system`
消息注入到主 System Prompt 之后,内容前缀为 `【项目上下文：AGENTS.md】`。

- 仅在会话首次加载时注入一次,并随会话事件日志一起持久化。
- 后续轮次与 `/resume` 恢复时直接复用该消息,不再重复读取,避免破坏模型缓存。
- 压缩上下文时会保留这条 system 消息;可用 `[session] agents_max_chars` 控制长度。

### MCP 服务器

MCP 配置读取当前项目目录的 `.mcp.json`(可在 `[mcp] config_file` 修改)。
TUI 启动后通过后台 worker 异步连接 MCP Server,不阻塞界面;右侧边栏动态显示:

- 每个 Server 的连接状态、传输方式、已发现工具名;
- 连接错误或配置解析错误;
- `/mcp` 命令可在对话区查看简要状态。

连接超时、调用超时、工具名长度和结果长度分别由 `[mcp] connect_timeout /
call_timeout / max_tool_name_length / max_result_chars` 控制。

### Skills(Agent Skills 规范)

启动时以**当前工作目录**为项目根目录, 扫描 `.agents/skills/<skill>/SKILL.md`。
发现阶段只解析 YAML Frontmatter 的 `name` / `description`, 注入 System Prompt;
正文和附件只有在 LLM 调用 `loadSkill` 时才进入上下文。

如需加载项目外部的 Skill, 在 `config.ini` 的 `[skills] extra_dirs` 中配置额外
Skill 目录(多个用逗号或分号分隔), 例如:

```ini
[skills]
extra_dirs = D:\ZDJ\opencode\office\.agents\skills
```

项目内 `.agents/skills` 优先; 同名 Skill 以先发现者为准。`createSkill` 始终写入
项目内的 `.agents/skills`。

```text
<项目根>/.agents/skills/
└── my-skill/
    ├── SKILL.md          # 必须以 --- 开头, 声明 name 和 description
    └── references/
        └── guide.md
```

`loadSkill(name)` 返回 SKILL.md 全文; `loadSkill(name, filename)` 读取附件,
支持 Skill 相对路径、项目相对路径、绝对路径; 只给文件名时递归搜索,
同名文件多个时返回候选路径。读取范围严格限制在对应 Skill 目录内。

`createSkill(name, skillContext)` 在 `.agents/skills/<name>/` 下创建 SKILL.md:
`name` 会规范为小写字母/数字/连字符格式, `skillContext` 会被规范为包含
`name` / `description` 的 YAML Frontmatter + 正文; 目标 Skill 已存在时只返回提示,
不会覆盖原内容。额外的 `references/`、`scripts/` 等文件由 fileOps 工具继续创建。

### Office 文件(OfficeCli)

`officeCli(args, timeout?, cwd?)` 通过 `subprocess` 调用同仓库的
`OfficeCli/officecli-win-x64.exe`, 支持 `create` / `add` / `set` / `view` / `validate`
等全部子命令, 可生成 PPT、Word、Excel 文件。示例:

```text
officeCli ["create", "slides.pptx"]
officeCli ["add", "slides.pptx", "/", "--type", "slide", "--prop", "title=Q4 Report"]
officeCli ["add", "slides.pptx", "/slide[1]", "--type", "shape", "--prop", "text=Revenue 25%"]
officeCli ["view", "slides.pptx", "stats"]
```

可执行文件按以下顺序查找: 环境变量 `OFFICECLI_PATH`、
`sAgent`/上级项目目录下的 `OfficeCli/officecli-win-x64.exe`、系统 `PATH`。
详细命令语法见 `OfficeCli/OfficeCli操作说明.md`, 也可调用 `officeCli ["help", ...]`。

### 事件契约(core.events)

`Agent.run_turn(prompt, sink)` 阻塞执行一轮,经 `sink` 依次推送:

| 事件 | 语义 | TUI 行为 |
| --- | --- | --- |
| `TurnStarted` | 用户提交 | transcript 写入用户消息,右侧面板复位 |
| `TextDelta` | 回复增量 | 右侧"实时回复"追加 |
| `ReasoningDelta` | 思考增量 | 右侧"思考过程"追加(Ctrl+T 折叠) |
| `ToolCallStarted` / `ToolCallFinished` | 工具执行 | 右侧工具面板 / transcript 工具面板 |
| `AssistantMessage` | 最终回复落定 | transcript 写入 Markdown 渲染 |
| `TurnFinished` | 本轮结束 | 恢复输入框 |
| `ErrorEvent` | 错误(用户可读文案) | transcript 红色提示 |
| `ContextStatus` | 当前上下文占用 | 底部状态栏显示 k / 窗口 / 百分比 |
| `ContextWarning` | 达到 60% 阈值 | transcript 红色警告 |
| `CompactionStarted` | 开始 `/compact` | 显示压缩提示 |
| `CompactionFinished` | 压缩成功 | 弹出压缩前后对照面板 |
| `CompactionFailed` | 压缩失败(原文保留) | 红色错误并恢复输入 |
| `McpStatus` | MCP 加载/连接状态 | 刷新右侧 MCP 边栏与 `/mcp` 状态 |

运行期错误全部转为 `ErrorEvent`,UI 层无需 try/except。

### 线程模型

TUI 在 `@work(thread=True)` worker 中调用阻塞的 `run_turn`;
MCP 连接使用独立的 `@work(thread=True, group="mcp")` worker,启动后异步加载,
事件经线程安全的 `post_message(AgentEventMsg)` 回 UI 线程后更新 widget。
未来 Web/Desktop 界面只需: 在自己的运行时里调用 `run_turn` / `load_mcp`
并消费同一事件流。

### 配置项

配置文件按段组织,所有键都可省略并使用内置默认值:

| 段 | 主要配置 |
| --- | --- |
| `[api]` | `key` `base_url` `model` `timeout` `connect_timeout` `max_tool_rounds` `context_window` `stream_usage` |
| `[context]` | `dir` `compact_threshold` `compact_target_tokens` `compact_max_tokens` `recall_*` |
| `[skills]` | `extra_dirs`(项目外额外 Skill 目录,逗号/分号分隔) |
| `[session]` | `dir` `auto_save` `agents_file` `agents_max_chars` |
| `[mcp]` | `config_file` `connect_timeout` `call_timeout` `max_tool_name_length` `max_result_chars` |
| `[tools]` | 文件读取上限、RunCli/OfficeCli 超时与输出截断、网页抓取/搜索超时与结果长度 |
| `[tui]` | `transcript_max_lines` `thinking_visible` |
| `[search]` | `baidu_qianfan_api_key` |

## 工具(19 个)

`getDate`(本地 date 命令) `isLeapYear` `getToolsDirectory`(sAgent 根目录)
`listDirectory` `getFileType` `readFile`(纯文本, 默认截断 20000 字符, 可由 `[tools] file_read_max_chars` 配置)
`createFile`(含自动建目录) `editFile`(write/append/replace)
`createDirectory` `deleteDirectory`(rmtree, 防删根目录/自身) `deleteFile` `renameItem`
`RunCli`(subprocess 列表形式执行本地命令, 不经过 Shell)
`fetchWeb`(curl 参数列表调用抓网页 → trafilatura 提取正文转 Markdown,保留标题/段落/列表/表格/链接,
去除导航/广告/页脚;覆盖超时/DNS/HTTP 状态/空内容/提取失败分支)
`searchWeb`(百度千帆 /v2/ai_search/web_search,key 读 config.ini `[search]` 或环境变量 BAIDU_QIANFAN_API_KEY,
返回摘要+参考来源标题/URL;覆盖缺配置/无效 Key/超时/网络失败/接口错误/空结果分支)
`loadSkill`(按需加载 Skill 的 SKILL.md 全文或 Skill 目录内附件)
`createSkill`(按 Agent Skills 规范创建新 Skill, 自动生成 Frontmatter, 不覆盖已有 Skill)
`recallContext`(在 `.agents/context/` 的 JSONL 归档中按关键词检索原始上下文)
`officeCli`(调用 OfficeCli 生成/编辑/读取/校验 .pptx/.docx/.xlsx; 自动查找上级 OfficeCli 目录, 也可用 `OFFICECLI_PATH` 指定)

新增工具: 在 `core/tools/` 写实现 + `ToolSpec` 注册即可,校验与兜底由 `make_handler` 统一处理。

## 关键实现要点(继承自 chat3.py)

1. assistant 消息回传**标准格式** `tool_calls`: `{id, type: "function", function: {name, arguments}}`(扁平格式会导致 422)
2. 思考模型(如 deepseek-flash)的 `reasoning_content` 需随 assistant 消息回传,否则下一轮报 400
3. 单轮流式: SSE 逐行解析 `data:` 帧,`tool_calls` 按 `index` 聚合完整后一次性分发
4. 工具往返上限默认 10(`[api] max_tool_rounds`),请求失败时整轮回滚历史
