"""RunCli 工具: 让 LLM 通过 function calling 调用本地任意命令行程序(CLI)。

使用 subprocess 列表形式(shell=False)执行, 避免 Shell 注入;
返回 stdout(stderr)/退出码, 并对超长输出做截断以保护上下文。
"""

import locale
import os
import subprocess
from typing import List, Sequence, Tuple

from .base import ToolRegistry, ToolSpec, make_handler

DEFAULT_TIMEOUT = 30
MAX_TIMEOUT = 300
MAX_OUTPUT_CHARS = 4000
DEFAULT_TIMEOUT_RUNTIME = DEFAULT_TIMEOUT
MAX_TIMEOUT_RUNTIME = MAX_TIMEOUT
MAX_OUTPUT_CHARS_RUNTIME = MAX_OUTPUT_CHARS

def _encoding() -> str:
    return locale.getpreferredencoding(False) or "utf-8"


def _normalize_args(args) -> List[str]:
    if args is None:
        return []
    if isinstance(args, (str, bytes)) or not isinstance(args, Sequence):
        return [str(args)]
    return [str(item) for item in args]


def _truncate(text: str, label: str) -> Tuple[str, bool]:
    limit = MAX_OUTPUT_CHARS_RUNTIME
    if len(text) <= limit:
        return text, False
    head = limit * 2 // 3
    tail = limit - head
    omitted = len(text) - head - tail
    return (
        f"{text[:head]}\n...[已截断: {label}省略了 {omitted} 个字符]...\n{text[-tail:]}",
        True,
    )


def run_cli(command: str, args=None, timeout: int = 0) -> str:
    """执行本地命令,返回 stdout/stderr 与退出码。"""
    argv = [command, *_normalize_args(args)]
    try:
        timeout = int(timeout)
    except (TypeError, ValueError):
        return f"参数错误: timeout 必须是整数秒数,收到 {timeout!r}。"
    if timeout <= 0:
        timeout = DEFAULT_TIMEOUT_RUNTIME
    timeout = min(timeout, MAX_TIMEOUT_RUNTIME)

    encoding = _encoding()
    try:
        result = subprocess.run(
            argv,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"执行失败: 命令超时被终止(超过 {timeout} 秒)。可尝试缩短输出或减小 timeout 参数后重试。"
    except FileNotFoundError:
        return f"执行失败: 未找到命令 {command!r},请确认本地已安装且在 PATH 中。"
    except (OSError, subprocess.SubprocessError) as exc:
        return f"执行失败: {exc}"

    stdout_text = (result.stdout or b"").decode(encoding, errors="replace").strip()
    stderr_text = (result.stderr or b"").decode(encoding, errors="replace").strip()
    stdout_text, stdout_truncated = _truncate(stdout_text, "标准输出")
    stderr_text, stderr_truncated = _truncate(stderr_text, "标准错误")

    notes = []
    if stdout_truncated or stderr_truncated:
        notes.append(
            f"(输出已截断: 每路输出最多保留 {MAX_OUTPUT_CHARS_RUNTIME} 字符,超出部分已省略)"
        )
    if result.returncode == 0:
        notes.append("(命令执行成功)")
    else:
        notes.append(f"(命令返回非零退出码,可能执行未成功,请结合 stderr 判断)")

    lines = [
        f"命令: {' '.join(argv)}",
        f"退出码: {result.returncode}",
        f"--- stdout ---\n{stdout_text if stdout_text else '(空)'}",
        f"--- stderr ---\n{stderr_text if stderr_text else '(空)'}",
        "\n".join(notes),
    ]
    return "\n".join(lines)


def register(
    registry: ToolRegistry,
    default_timeout: int = DEFAULT_TIMEOUT,
    max_timeout: int = MAX_TIMEOUT,
    max_output_chars: int = MAX_OUTPUT_CHARS,
) -> None:
    global DEFAULT_TIMEOUT_RUNTIME, MAX_TIMEOUT_RUNTIME, MAX_OUTPUT_CHARS_RUNTIME
    DEFAULT_TIMEOUT_RUNTIME = default_timeout
    MAX_TIMEOUT_RUNTIME = max_timeout
    MAX_OUTPUT_CHARS_RUNTIME = max_output_chars
    registry.register(
        ToolSpec(
            name="RunCli",
            description=(
                "调用本地命令行程序(CLI)。传入程序名 command 和参数列表 args, "
                "返回 stdout、stderr 和退出码。适用于 dir/ls、ping、pip、git 等任意已安装命令。"
                "命令以当前用户权限执行,请勿发起长时间阻塞的交互式命令。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的程序名称,例如 ping、git、dir"},
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "传给程序的参数列表,每个参数是一个独立的字符串元素,例如 [\"-n\", \"1\"]",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": f"最长执行时间(秒),默认 {default_timeout},超过会被终止 最大 {max_timeout}",
                    },
                },
                "required": ["command"],
            },
            handler=make_handler(run_cli, required=("command",), optional=("args", "timeout")),
        )
    )
