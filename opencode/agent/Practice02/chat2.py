import configparser
import json
import locale
import os
import subprocess
import sys
from pathlib import Path

import requests

CONFIG_FILE = Path(__file__).resolve().with_name("config.ini")
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
TIMEOUT = 60
MAX_TOOL_ROUNDS = 5

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "getDate",
            "description": "获取当前电脑的日期和时间。通过调用本地 date 命令获取,返回当前日期和时间字符串。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "isLeapYear",
            "description": "判断指定年份是否是闰年。用 Python 代码计算,返回该年份是否为闰年的结论。",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "要判断的年份,例如 2024",
                    }
                },
                "required": ["year"],
            },
        },
    },
]

for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


class ConfigError(Exception):
    pass


def pick(config, option: str, env: str, default: str = "") -> str:
    if config is not None and config.has_option("api", option):
        value = config.get("api", option).strip()
        if value:
            return value
    value = os.environ.get(env, "").strip()
    return value or default


def load_config():
    config = configparser.ConfigParser()
    if CONFIG_FILE.is_file():
        try:
            config.read(CONFIG_FILE, encoding="utf-8-sig")
        except configparser.Error as exc:
            raise ConfigError(f"config.ini 解析失败: {exc}")

    api_key = pick(config, "key", "CHAT_API_KEY")
    if not api_key:
        if not CONFIG_FILE.is_file():
            raise ConfigError(f"未找到配置文件 {CONFIG_FILE},请创建它并填写 api.key。")
        raise ConfigError(
            f"未找到 API Key,请在 {CONFIG_FILE} 中设置 api.key。\n"
            "示例:\n[api]\nkey = sk-xxxx"
        )

    base_url = pick(config, "base_url", "CHAT_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    model = pick(config, "model", "CHAT_MODEL", DEFAULT_MODEL)
    return api_key, base_url, model


def read_prompt():
    try:
        line = input("请输入提示词: ")
    except (EOFError, KeyboardInterrupt):
        print("\n已取消。")
        return None
    return line.strip()


def run_date_command() -> str:
    """调用本地 date 命令获取日期和时间(不用 python 时间库)。"""
    if os.name == "nt":
        # /u 让 cmd 以 UTF-16 输出,避免本地代码页把日期中的中文变成 ??
        command = 'cmd /u /c "date /t & time /t"'
        encoding = "utf-16-le"
    else:
        command = "date"
        encoding = locale.getpreferredencoding(False) or "utf-8"
    try:
        result = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"执行本地 date 命令失败: {exc}"

    stdout = (result.stdout or b"").decode(encoding, errors="replace")
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if lines:
        return " ".join(lines)

    stderr = (result.stderr or b"").decode(encoding, errors="replace").strip()
    if result.returncode != 0:
        return f"date 命令执行失败 (退出码 {result.returncode}): {stderr or '无输出'}"
    return stderr or "date 命令没有输出"


def is_leap_year(year: int) -> bool:
    """用 Python 代码判断闰年: 能被4整除,但不能被100整除,除非也能被400整除。"""
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def check_leap_year(arguments: str) -> str:
    try:
        args = json.loads(arguments) if arguments.strip() else {}
    except ValueError:
        return "参数解析失败: arguments 不是合法的 JSON。"
    if not isinstance(args, dict) or args.get("year") is None:
        return "参数错误: 缺少必填参数 year。"
    try:
        year = int(args["year"])
    except (TypeError, ValueError):
        return f"参数错误: year 必须是整数,收到 {args['year']!r}。"
    if is_leap_year(year):
        return f"{year}年是闰年。"
    return f"{year}年不是闰年。"


def dispatch_tool(call: dict) -> str:
    name, arguments = call_fields(call)
    if name == "getDate":
        return run_date_command()
    if name == "isLeapYear":
        return check_leap_year(arguments or "")
    return f"未知工具: {name}"


def open_stream(api_key: str, base_url: str, model: str, messages: list):
    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "stream": True,
            "tools": TOOLS,
        },
        stream=True,
        timeout=(10, TIMEOUT),
    )
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        try:
            resp.content
        except requests.exceptions.RequestException:
            pass
        resp.close()
        raise
    resp.encoding = "utf-8"
    return resp


def iter_events(resp):
    """解析 SSE 流,产出 ("text", 片段)、("reasoning", 思考片段) 与 ("tool_calls", 工具调用列表)。"""
    tool_calls = {}
    for line in resp.iter_lines(decode_unicode=True):
        if not line:
            continue
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if payload == "[DONE]":
            break
        try:
            data = json.loads(payload)
        except ValueError:
            continue
        if not isinstance(data, dict):
            continue
        if data.get("error"):
            err = data["error"]
            message = err.get("message") if isinstance(err, dict) else err
            raise ValueError(f"接口返回错误: {message}")
        choices = data.get("choices")
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        content = delta.get("content")
        if isinstance(content, str) and content:
            yield "text", content
        reasoning = delta.get("reasoning_content")
        if isinstance(reasoning, str) and reasoning:
            yield "reasoning", reasoning
        for item in delta.get("tool_calls") or []:
            if not isinstance(item, dict):
                continue
            index = item.get("index", 0)
            entry = tool_calls.setdefault(
                index,
                {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
            )
            if item.get("id"):
                entry["id"] = item["id"]
            function = item.get("function") or {}
            if function.get("name"):
                entry["function"]["name"] += function["name"]
            if function.get("arguments"):
                entry["function"]["arguments"] += function["arguments"]
    if tool_calls:
        yield "tool_calls", [tool_calls[key] for key in sorted(tool_calls)]


def call_fields(call: dict):
    """从标准格式 function 嵌套(或旧扁平格式)中取出工具名与参数。"""
    function = call.get("function")
    if isinstance(function, dict):
        return function.get("name") or "", function.get("arguments") or ""
    return call.get("name") or "", call.get("arguments") or ""


def error_detail(response) -> str:
    if response is None:
        return ""
    try:
        err = response.json()["error"]
        message = err.get("message") if isinstance(err, dict) else err
    except (ValueError, KeyError, TypeError, AttributeError):
        return ""
    if isinstance(message, str) and message.strip():
        return message.strip()[:300]
    return ""


def http_error_message(exc) -> str:
    response = exc.response
    status = response.status_code if response is not None else 0
    if status in (401, 403):
        msg = "错误: API Key 无效或没有权限,请检查 config.ini。"
    elif status == 429:
        msg = "错误: 请求过于频繁或额度不足,请稍后重试。"
    elif status == 404:
        msg = "错误: 接口地址或模型不存在,请检查 config.ini 中的 base_url / model。"
    elif status >= 500:
        msg = "错误: 服务端暂时不可用,请稍后重试。"
    else:
        msg = f"错误: 调用失败 (HTTP {status}),请稍后重试。"
    detail = error_detail(response)
    if detail:
        msg = f"{msg}\n详情: {detail}"
    return msg


def main() -> int:
    try:
        api_key, base_url, model = load_config()
    except ConfigError as exc:
        print(f"错误: {exc}")
        return 1

    history = []

    def fail(msg: str) -> int:
        print(msg)
        return 1

    while True:
        user_prompt = read_prompt()
        if user_prompt is None:
            return 1
        if not user_prompt:
            print("错误: 提示词为空,程序退出。")
            return 1

        history.append({"role": "user", "content": user_prompt})
        rounds = 0

        while True:
            resp = None
            started = False
            reply_parts = []
            reasoning_parts = []
            tool_calls = []

            try:
                resp = open_stream(api_key, base_url, model, history)
                if rounds == 0:
                    print("---", flush=True)

                events = 0
                for kind, value in iter_events(resp):
                    if kind == "text":
                        print(value, end="", flush=True)
                        reply_parts.append(value)
                        started = True
                        events += 1
                    elif kind == "reasoning":
                        reasoning_parts.append(value)
                    else:
                        tool_calls = value
                        events += 1
                if started:
                    print()
                if events == 0:
                    return fail("错误: 模型返回了空回复。")
            except KeyboardInterrupt:
                return fail("\n已取消。")
            except requests.exceptions.Timeout:
                return fail(f"错误: 请求超时 (>{TIMEOUT}s),请稍后重试。")
            except requests.exceptions.HTTPError as exc:
                return fail(http_error_message(exc))
            except requests.exceptions.RequestException:
                return fail("错误: 网络连接失败或传输中断,请检查网络后重试。")
            except ValueError as exc:
                return fail(f"错误: {exc}")
            finally:
                if resp is not None:
                    resp.close()

            reasoning_text = "".join(reasoning_parts)

            if not tool_calls:
                final_msg = {"role": "assistant", "content": "".join(reply_parts)}
                if reasoning_text:
                    final_msg["reasoning_content"] = reasoning_text
                history.append(final_msg)
                break

            assistant_msg = {"role": "assistant", "tool_calls": tool_calls}
            text = "".join(reply_parts)
            if text:
                assistant_msg["content"] = text
            if reasoning_text:
                assistant_msg["reasoning_content"] = reasoning_text
            history.append(assistant_msg)

            for call in tool_calls:
                name, _ = call_fields(call)
                result = dispatch_tool(call)
                print(f"[tool] {name} -> {result}", flush=True)
                history.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id") or "",
                        "content": result,
                    }
                )

            rounds += 1
            if rounds > MAX_TOOL_ROUNDS:
                return fail("错误: 工具调用轮次过多,程序退出。")


if __name__ == "__main__":
    sys.exit(main())
