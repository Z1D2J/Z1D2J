"""OfficeCli 工具: 调用本地 OfficeCli 可执行文件生成/编辑/检查 Office 文件。

OfficeCli 是单文件 CLI, 支持 .pptx / .docx / .xlsx; 本工具只负责定位可执行文件、
安全地传递参数并返回输出。具体的建文件、加幻灯片、写表格等语法由 LLM 通过
`officeCli` 的 help/子命令自行组合, 详细说明见工具描述中的本地操作文档。
"""

import json
import locale
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import List, Sequence, Tuple

from .base import ToolRegistry, ToolSpec, make_handler

DEFAULT_TIMEOUT = 60
MAX_TIMEOUT = 300
MAX_OUTPUT_CHARS = 8000
DEFAULT_TIMEOUT_RUNTIME = DEFAULT_TIMEOUT
MAX_TIMEOUT_RUNTIME = MAX_TIMEOUT
MAX_OUTPUT_CHARS_RUNTIME = MAX_OUTPUT_CHARS

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXE_NAME = "officecli-win-x64.exe"
GUIDE_NAME = "OfficeCli操作说明.md"


def _candidate_executables() -> List[Path]:
    candidates: List[Path] = []

    configured = os.environ.get("OFFICECLI_PATH", "").strip()
    if configured:
        candidates.append(Path(configured).expanduser())

    project_parent = PROJECT_ROOT.parent
    workspace = project_parent.parent
    for base in (PROJECT_ROOT, project_parent, workspace, Path.cwd(), Path.cwd().parent):
        candidates.append(base / "OfficeCli" / EXE_NAME)
        candidates.append(base / EXE_NAME)

    return candidates


def find_executable() -> Path | None:
    for candidate in _candidate_executables():
        try:
            if candidate.is_file():
                return candidate.resolve()
        except OSError:
            continue
    for name in ("officecli", "officecli.exe", EXE_NAME):
        found = shutil.which(name)
        if found:
            return Path(found).resolve()
    return None


def find_guide(executable: Path | None) -> Path | None:
    bases = []
    if executable is not None:
        bases.append(executable.parent)
    bases.extend(candidate.parent for candidate in _candidate_executables())
    for base in bases:
        try:
            guide = base / GUIDE_NAME
            if guide.is_file():
                return guide.resolve()
        except OSError:
            continue
    return None


def _encoding() -> str:
    return locale.getpreferredencoding(False) or "utf-8"


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", _encoding(), "gbk"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


def _normalize_args(args) -> List[str]:
    if args is None:
        return []
    if isinstance(args, str):
        text = args.strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except ValueError:
                parsed = None
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        items = shlex.split(text, posix=False)
        return [item.strip().strip("\"'") for item in items]
    if isinstance(args, (bytes,)) or not isinstance(args, Sequence):
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
        f"{text[:head]}\n...[截断: {label}被省略 {omitted} 字符]...\n{text[-tail:]}",
        True,
    )


def office_cli(args, timeout: int = 0, cwd: str = "") -> str:
    executable = find_executable()
    if executable is None:
        return (
            "错误: 未找到 OfficeCli 可执行文件 officecli-win-x64.exe。"
            "请将 OfficeCli 目录放在项目上级目录, 或设置环境变量 OFFICECLI_PATH 指向该 exe。"
        )

    argv = _normalize_args(args)
    if not argv:
        return "参数错误: args 不能为空, 例如 [\"create\", \"report.pptx\"]。"

    try:
        timeout = int(timeout)
    except (TypeError, ValueError):
        return f"参数错误: timeout 必须是整数秒数,收到 {timeout!r}。"
    if timeout <= 0:
        timeout = DEFAULT_TIMEOUT_RUNTIME
    timeout = min(timeout, MAX_TIMEOUT_RUNTIME)

    workdir = Path(cwd).expanduser() if cwd else Path.cwd()
    if cwd and not workdir.is_dir():
        return f"参数错误: cwd 不是有效目录: {workdir}"

    try:
        result = subprocess.run(
            [str(executable), *argv],
            shell=False,
            cwd=str(workdir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"执行失败: OfficeCli 命令超时被终止(超过 {timeout} 秒)。"
    except FileNotFoundError:
        return f"执行失败: 未找到 OfficeCli 可执行文件: {executable}"
    except (OSError, subprocess.SubprocessError) as exc:
        return f"执行失败: {exc}"

    stdout_text, stdout_truncated = _truncate(_decode(result.stdout or b"").strip(), "标准输出")
    stderr_text, stderr_truncated = _truncate(_decode(result.stderr or b"").strip(), "标准错误")

    notes = []
    if stdout_truncated or stderr_truncated:
        notes.append(
            f"(输出已截断: 每路输出最多保留 {MAX_OUTPUT_CHARS_RUNTIME} 字符)"
        )
    notes.append("(执行成功)" if result.returncode == 0 else f"(退出码 {result.returncode}, 请结合 stderr 判断)")

    return "\n".join(
        [
            f"OfficeCli: {' '.join(argv)}",
            f"工作目录: {workdir}",
            f"退出码: {result.returncode}",
            f"--- stdout ---\n{stdout_text or '(空)'}",
            f"--- stderr ---\n{stderr_text or '(空)'}",
            "\n".join(notes),
        ]
    )


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
    executable = find_executable()
    guide = find_guide(executable)
    location = f"当前可执行文件: {executable}" if executable else "未自动找到可执行文件, 可通过 OFFICECLI_PATH 指定。"
    doc_hint = f"详细语法见本地文档: {guide}" if guide else "详细语法可调用 [\"help\"] 或 [\"help\", \"pptx\", \"slide\"]。"

    registry.register(
        ToolSpec(
            name="officeCli",
            description=(
                "调用 OfficeCli 生成、编辑、读取和校验 .pptx / .docx / .xlsx 文件。"
                "args 是传给 officecli 的参数数组, 常用示例: "
                "[\"create\", \"slides.pptx\"]; "
                "[\"add\", \"slides.pptx\", \"/\", \"--type\", \"slide\", \"--prop\", \"title=Q4 Report\"]; "
                "[\"add\", \"slides.pptx\", \"/slide[1]\", \"--type\", \"shape\", \"--prop\", \"text=Revenue 25%\", \"--prop\", \"x=2cm\", \"--prop\", \"y=5cm\"]; "
                "[\"view\", \"slides.pptx\", \"stats\"]; [\"help\", \"pptx\", \"slide\"]。"
                "生成 PPT 前可先执行 [\"load_skill\", \"pptx\"] 获取专业排版规则"
                "(路演用 pitch-deck, Morph 动画用 morph-ppt)。"
                "若文件马上要被其他程序读取或交付, 再执行 [\"close\", \"文件名\"] 刷新到磁盘。"
                "相对路径按 cwd 解析, 默认当前工作目录。"
                f"{location}{doc_hint}"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "传给 officecli 的参数数组, 例如 [\"create\", \"report.pptx\"]",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": f"最长执行时间(秒), 默认 {default_timeout}, 最大 {max_timeout}",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "可选, 命令工作目录; 相对文件路径基于该目录。默认当前工作目录",
                    },
                },
                "required": ["args"],
            },
            handler=make_handler(
                office_cli, required=("args",), optional=("timeout", "cwd")
            ),
        )
    )
