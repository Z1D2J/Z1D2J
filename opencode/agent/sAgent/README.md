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
配置: `config.ini` 的 `[api]` 段填 `key / base_url / model`(未填时读环境变量 `CHAT_API_KEY` 等)。

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
├── agent.py         L3 编排 (多轮工具往返, 事件推送, 历史维护)
├── llm/
│   ├── client.py    L1 流式 HTTP 客户端 (错误翻译成中文文案)
│   └── (SSE 解析内置)
└── tools/
    ├── base.py      L2 注册框架 (ToolSpec / ToolRegistry / make_handler)
    ├── builtin.py   L2 getDate, isLeapYear
    └── file_ops.py  L2 文件工具 10 个
```

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

运行期错误全部转为 `ErrorEvent`,UI 层无需 try/except。

### 线程模型

TUI 在 `@work(thread=True)` worker 中调用阻塞的 `run_turn`;
事件经线程安全的 `post_message(AgentEventMsg)` 回 UI 线程后更新 widget。
未来 Web/Desktop 界面只需: 在自己的运行时里调用 `run_turn` 并消费同一事件流。

## 工具(12 个)

`getDate`(本地 date 命令) `isLeapYear` `getToolsDirectory`(sAgent 根目录)
`listDirectory` `getFileType` `readFile`(纯文本, 截断 20000 字符)
`createFile`(含自动建目录) `editFile`(write/append/replace)
`createDirectory` `deleteDirectory`(rmtree, 防删根目录/自身) `deleteFile` `renameItem`

新增工具: 在 `core/tools/` 写实现 + `ToolSpec` 注册即可,校验与兜底由 `make_handler` 统一处理。

## 关键实现要点(继承自 chat3.py)

1. assistant 消息回传**标准格式** `tool_calls`: `{id, type: "function", function: {name, arguments}}`(扁平格式会导致 422)
2. 思考模型(如 deepseek-flash)的 `reasoning_content` 需随 assistant 消息回传,否则下一轮报 400
3. 单轮流式: SSE 逐行解析 `data:` 帧,`tool_calls` 按 `index` 聚合完整后一次性分发
4. 工具往返上限 `MAX_TOOL_ROUNDS=10`,请求失败时整轮回滚历史
