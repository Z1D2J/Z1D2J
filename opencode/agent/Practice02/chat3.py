import configparser
import json
import locale
import mimetypes
import os
import shutil
import subprocess
import sys
from pathlib import Path

import requests

CONFIG_FILE = Path(__file__).resolve().with_name("config.ini")
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
TIMEOUT = 60
MAX_TOOL_ROUNDS = 10
MAX_READ_CHARS = 20000

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
    {
        "type": "function",
        "function": {
            "name": "getToolsDirectory",
            "description": "获取当前工具(本程序)所在目录的绝对路径。无参数。",
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
            "name": "listDirectory",
            "description": "列出指定目录下的所有文件和子目录。返回每个条目的类型([目录]/[文件])、名称,文件附带字节大小。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要列出内容的目录路径",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "getFileType",
            "description": "获取指定文件的文件类型信息:是文件还是目录、扩展名、MIME 类型和字节大小。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件或目录的路径",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "readFile",
            "description": "获取指定文件的内容,仅支持纯文本格式文件。返回文件的文本内容(过长时截断)。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要读取的纯文本文件路径",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "createFile",
            "description": "根据指定的目录和文件名创建新文件,同时支持创建新目录(目录不存在时自动逐级创建)。可选写入初始内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "新文件所在目录,不存在时会自动创建",
                    },
                    "filename": {
                        "type": "string",
                        "description": "新文件的文件名,例如 note.txt",
                    },
                    "content": {
                        "type": "string",
                        "description": "写入文件的初始内容,默认为空字符串",
                    },
                },
                "required": ["directory", "filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "editFile",
            "description": "编辑指定文件的内容,仅支持纯文本格式文件。mode 取值: write=用 content 覆盖整个文件; append=在文件末尾追加 content; replace=把文件中所有 old_text 替换为 new_text。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要编辑的纯文本文件路径",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["write", "append", "replace"],
                        "description": "编辑模式: write 覆盖写入 / append 追加 / replace 查找替换",
                    },
                    "content": {
                        "type": "string",
                        "description": "write 和 append 模式下要写入的内容",
                    },
                    "old_text": {
                        "type": "string",
                        "description": "replace 模式下要被替换的原文本",
                    },
                    "new_text": {
                        "type": "string",
                        "description": "replace 模式下替换后的新文本",
                    },
                },
                "required": ["path", "mode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "createDirectory",
            "description": "创建新目录,支持同时创建尚不存在的上级目录。目录已存在时不报错。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要创建的目录路径",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deleteDirectory",
            "description": "删除指定目录及其全部内容(支持删除非空目录)。删除后不可恢复,请谨慎调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要删除的目录路径",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deleteFile",
            "description": "删除指定的文件。删除后不可恢复,请谨慎调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要删除的文件路径",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "renameItem",
            "description": "重命名或移动文件和目录:把 old_path 重命名为 new_path(可跨目录移动)。",
            "parameters": {
                "type": "object",
                "properties": {
                    "old_path": {
                        "type": "string",
                        "description": "原文件或目录路径",
                    },
                    "new_path": {
                        "type": "string",
                        "description": "重命名后的文件或目录路径(可包含新的目录位置)",
                    },
                },
                "required": ["old_path", "new_path"],
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


def parse_arguments(arguments: str):
    try:
        args = json.loads(arguments) if arguments.strip() else {}
    except ValueError:
        return None
    return args if isinstance(args, dict) else None


def make_handler(func, required=(), optional=()):
    def handler(arguments: str) -> str:
        args = parse_arguments(arguments)
        if args is None:
            return "参数解析失败: arguments 不是合法的 JSON 对象。"
        kwargs = {}
        for key in required:
            value = args.get(key)
            if value is None or (isinstance(value, str) and not value.strip()):
                return f"参数错误: 缺少必填参数 {key}。"
            kwargs[key] = value
        for key in optional:
            if key in args and args[key] is not None:
                kwargs[key] = args[key]
        try:
            return func(**kwargs)
        except OSError as exc:
            return f"文件操作失败: {exc}"

    return handler


def load_text_file(path: Path):
    data = path.read_bytes()
    if b"\x00" in data:
        return None, "该文件疑似二进制文件,仅支持纯文本格式。"
    encodings = ["utf-8", locale.getpreferredencoding(False) or "utf-8", "gbk"]
    for encoding in encodings:
        try:
            return data.decode(encoding), None
        except (UnicodeDecodeError, LookupError):
            continue
    return None, "文件解码失败,可能不是纯文本格式文件。"


def get_tools_directory() -> str:
    return str(Path(__file__).resolve().parent)


def list_directory(path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"错误: 目录不存在: {p}"
    if not p.is_dir():
        return f"错误: 路径不是目录: {p}"
    entries = sorted(p.iterdir(), key=lambda e: (0 if e.is_dir() else 1, e.name.lower()))
    if not entries:
        return "目录为空。"
    lines = []
    for entry in entries:
        if entry.is_dir():
            lines.append(f"[目录] {entry.name}")
        else:
            try:
                size = entry.stat().st_size
            except OSError:
                size = -1
            lines.append(f"[文件] {entry.name} ({size} 字节)")
    return "\n".join(lines)


def get_file_type(path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"错误: 路径不存在: {p}"
    if p.is_dir():
        return f"类型: 目录\n路径: {p}"
    if not p.is_file():
        return f"类型: 特殊文件(设备/管道/链接等)\n路径: {p}"
    mime, _ = mimetypes.guess_type(p.name)
    size = p.stat().st_size
    ext = p.suffix if p.suffix else "(无扩展名)"
    return (
        f"类型: 文件\n"
        f"扩展名: {ext}\n"
        f"MIME 类型: {mime or '未知'}\n"
        f"大小: {size} 字节\n"
        f"路径: {p}"
    )


def read_text_file(path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"错误: 文件不存在: {p}"
    if not p.is_file():
        return f"错误: 路径不是文件: {p}"
    text, err = load_text_file(p)
    if err:
        return f"错误: {err}"
    if len(text) > MAX_READ_CHARS:
        return (
            text[:MAX_READ_CHARS]
            + f"\n...(内容过长已截断,文件共 {len(text)} 字符)"
        )
    return text


def create_text_file(directory: str, filename: str, content: str = "") -> str:
    d = Path(directory).expanduser()
    target = d / filename
    if target.exists():
        return f"错误: 目标已存在: {target}"
    d.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"已创建文件: {target}(内容 {len(content)} 字符)"


def edit_text_file(
    path: str,
    mode: str,
    content: str = "",
    old_text: str = "",
    new_text: str = "",
) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"错误: 文件不存在: {p}"
    if not p.is_file():
        return f"错误: 路径不是文件: {p}"
    old_content, err = load_text_file(p)
    if err:
        return f"错误: {err}"
    if mode == "write":
        updated = content
    elif mode == "append":
        updated = old_content + content
    elif mode == "replace":
        if not old_text:
            return "错误: replace 模式需要提供 old_text。"
        if old_text not in old_content:
            return "错误: 在文件中未找到 old_text,替换失败。"
        updated = old_content.replace(old_text, new_text)
    else:
        return f"错误: 不支持的 mode: {mode!r},可选 write/append/replace。"
    p.write_text(updated, encoding="utf-8")
    return f"已更新文件: {p}(当前 {len(updated)} 字符)"


def create_directory(path: str) -> str:
    p = Path(path).expanduser()
    if p.is_dir():
        return f"目录已存在: {p}"
    p.mkdir(parents=True, exist_ok=True)
    return f"已创建目录: {p}"


def _guard_removable(p: Path):
    resolved = p.resolve()
    if resolved == Path(resolved.anchor):
        return f"错误: 不允许删除磁盘根目录: {resolved}"
    if resolved == Path(__file__).resolve().parent:
        return f"错误: 不允许删除工具自身目录: {resolved}"
    return None


def delete_directory(path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"错误: 目录不存在: {p}"
    if not p.is_dir():
        return f"错误: 路径不是目录: {p}(删除文件请改用 deleteFile)。"
    guard = _guard_removable(p)
    if guard:
        return guard
    count = sum(1 for _ in p.rglob("*"))
    shutil.rmtree(p)
    return f"已删除目录: {p}(含 {count} 个内部条目)"


def delete_file(path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"错误: 文件不存在: {p}"
    if not p.is_file():
        return f"错误: 路径不是文件: {p}(删除目录请改用 deleteDirectory)。"
    p.unlink()
    return f"已删除文件: {p}"


def rename_item(old_path: str, new_path: str) -> str:
    src = Path(old_path).expanduser()
    dst = Path(new_path).expanduser()
    if not src.exists():
        return f"错误: 原路径不存在: {src}"
    if dst.exists():
        return f"错误: 新路径已存在: {dst}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    return f"已重命名/移动: {src} -> {dst}"


FILE_TOOL_HANDLERS = {
    "getToolsDirectory": make_handler(get_tools_directory),
    "listDirectory": make_handler(list_directory, required=("path",)),
    "getFileType": make_handler(get_file_type, required=("path",)),
    "readFile": make_handler(read_text_file, required=("path",)),
    "createFile": make_handler(
        create_text_file,
        required=("directory", "filename"),
        optional=("content",),
    ),
    "editFile": make_handler(
        edit_text_file,
        required=("path", "mode"),
        optional=("content", "old_text", "new_text"),
    ),
    "createDirectory": make_handler(create_directory, required=("path",)),
    "deleteDirectory": make_handler(delete_directory, required=("path",)),
    "deleteFile": make_handler(delete_file, required=("path",)),
    "renameItem": make_handler(rename_item, required=("old_path", "new_path")),
}


def dispatch_tool(call: dict) -> str:
    name, arguments = call_fields(call)
    if name == "getDate":
        return run_date_command()
    if name == "isLeapYear":
        return check_leap_year(arguments or "")
    handler = FILE_TOOL_HANDLERS.get(name)
    if handler is not None:
        return handler(arguments or "")
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
