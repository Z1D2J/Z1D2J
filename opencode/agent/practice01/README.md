# chat.py — 多轮流式对话命令行工具

一个极简的大模型命令行客户端:读取本地 `config.ini` 中的 API Key,输入一句提示词,调用 OpenAI 兼容接口并**流式**打印模型回复,然后回到提示符继续下一轮,直到按下 `Ctrl+C` 结束。

## 功能

- API Key 从本地 `config.ini` 读取,不在代码里硬编码,也不用每次启动输入
- 多轮循环对话:输入提示词 → 调用模型 → 打印 `---` 分隔线 → 逐字流式输出回复 → 再次提示输入,`Ctrl+C` 退出
- 每次请求都会携带此前的完整对话记录(`user` / `assistant` 消息序列),模型能看到上文
- 兼容任何 OpenAI 风格的 `/v1/chat/completions` 服务(OpenAI、DeepSeek、Kimi、通义等)
- 所有失败场景均打印友好中文错误并以退出码 `1` 结束,不抛堆栈

## 环境要求

- Python 3.8+
- 依赖:`requests`

```bash
pip install requests
```

## 配置

在 `chat.py` 同目录下创建/编辑 `config.ini`:

```ini
; 本地配置,API Key 不要提交到仓库
[api]
key = sk-xxxxxxxx
base_url = https://api.openai.com/v1
model = gpt-4o-mini
```

| 配置项 | 说明 | 必填 | 默认值 |
| --- | --- | --- | --- |
| `key` | API Key | 是 | 无 |
| `base_url` | 接口地址(自动去掉末尾 `/`) | 否 | `https://api.openai.com/v1` |
| `model` | 模型名 | 否 | `gpt-4o-mini` |

同名环境变量可作为替代:`CHAT_API_KEY`、`CHAT_BASE_URL`、`CHAT_MODEL`。

**取值优先级:`config.ini` > 环境变量 > 内置默认值**(`key` 没有内置默认值,两者都缺失即报错)。

## 运行

```bash
python chat.py
```

示例输出:

```
请输入提示词: 用一句话介绍 Python
---
Python 是一门语法简洁、生态丰富、适用于从脚本到大型项目的通用编程语言。
```

每轮结束后回到 `请输入提示词:` 提示符,按 `Ctrl+C` 结束程序。

## 错误处理

| 场景 | 提示 |
| --- | --- |
| 缺少 `config.ini` | `未找到配置文件 .../config.ini,请创建它并填写 api.key。` |
| `key` 为空 | `未找到 API Key,请在 .../config.ini 中设置 api.key。` 并给出示例 |
| ini 语法错误 | `config.ini 解析失败: ...` |
| HTTP 401/403 | `API Key 无效或没有权限,请检查 config.ini。`(附接口返回详情) |
| HTTP 404 | `接口地址或模型不存在,请检查 config.ini 中的 base_url / model。` |
| HTTP 429 / 5xx | 限流或服务端故障,提示稍后重试 |
| 连接失败 / 传输中断 | `网络连接失败或传输中断,请检查网络后重试。` |
| 响应超时(连接 10s、读 60s) | `请求超时 (>60s),请稍后重试。` |
| 流中返回 error 对象 | `接口返回错误: <服务端信息>` |
| 模型返回空内容 | `模型返回了空回复。` |
| 提示词为空 / Ctrl+C | 友好提示后退出 |

失败时不会打印 `---` 分隔线(HTTP 错误在建流阶段就已捕获);若输出到一半断流,错误信息会换行接在已输出内容之后。

## 实现说明

1. `load_config()` 从 `config.ini` 读取 `key` / `base_url` / `model`
2. 主循环维护一个 `history` 列表:先追加本轮 `user` 消息,`open_stream()` 以 `stream=True` 发起 `POST /chat/completions`,请求体带 `"stream": true` 和完整的 `messages`
3. 打印 `---` 后,`iter_reply()` 逐行解析服务端的 SSE 事件(`data: {...}`),取出 `choices[0].delta.content`
4. 每个分片 `print(..., end="", flush=True)` 立即输出并累积到 `reply_parts`,遇 `data: [DONE]` 结束;随后把完整回复作为 `assistant` 消息追加进 `history`,供下一轮使用

## 安全提示

- `config.ini` 含真实密钥,请勿提交到仓库或分享;可将其加入 `.gitignore`
- 需要在临时环境覆盖配置时,优先使用环境变量而非改写文件
