"""上下文管理: Token 估算、原始上下文归档与关键词检索。

设计目标是简单、适合学生阅读:
- Token 优先使用模型 API 返回的 usage,拿不到时按字符粗略估算。
- 归档就是 JSONL: 一条消息一行,原样保存 role/content/tool_calls/tool 结果。
- 检索就是本地全文关键词匹配,不使用向量数据库或 Embedding。
"""

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

DEFAULT_CONTEXT_WINDOW = 128_000
COMPACT_THRESHOLD = 0.60
COMPACT_TARGET_TOKENS = 5_000
COMPACT_MAX_TOKENS = 6_500
CONTEXT_DIR = Path(".agents") / "context"
ARCHIVE_ID_PATTERN = re.compile(r"^\d{8}-\d{6}(?:-\d+)?$")
MAX_RECALL_MATCHES = 8
MAX_RECALL_CHARS = 8_000
MAX_RECALL_SNIPPET = 600

KNOWN_CONTEXT_WINDOWS = {
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4.1": 1_047_576,
    "gpt-4.1-mini": 1_047_576,
    "deepseek-chat": 128_000,
    "deepseek-reasoner": 128_000,
}


@dataclass(frozen=True)
class ContextUsage:
    tokens: int
    window: int
    percent: float
    default_window: bool


@dataclass(frozen=True)
class Archive:
    id: str
    path: Path
    created_at: datetime


def resolve_context_window(
    model: str, configured: Optional[int] = None
) -> Tuple[int, bool]:
    """返回 (上下文窗口大小, 是否使用了默认值)。"""
    if configured and configured > 0:
        return int(configured), False
    lowered = (model or "").casefold()
    for name, size in KNOWN_CONTEXT_WINDOWS.items():
        if name in lowered:
            return size, False
    return DEFAULT_CONTEXT_WINDOW, True


def estimate_text_tokens(text: str) -> int:
    """粗略估算 Token: 英文字符约 4 个 1 token,CJK 等字符约 1 个 1 token。"""
    if not text:
        return 0
    ascii_count = sum(1 for char in text if ord(char) < 128)
    non_ascii_count = len(text) - ascii_count
    return max(1, (ascii_count + 3) // 4 + non_ascii_count)


def _text_value(value) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or item))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return json.dumps(value, ensure_ascii=False)


def estimate_messages_tokens(messages: List[dict]) -> int:
    total = 0
    for message in messages:
        total += 4  # 每条消息的固定开销
        total += estimate_text_tokens(_text_value(message.get("content")))
        total += estimate_text_tokens(_text_value(message.get("reasoning_content")))
        if message.get("tool_calls"):
            total += estimate_text_tokens(
                json.dumps(message["tool_calls"], ensure_ascii=False)
            )
    return total


def estimate_tools_tokens(tools: List[dict]) -> int:
    if not tools:
        return 0
    return estimate_text_tokens(json.dumps(tools, ensure_ascii=False))


def _render_message_body(message: dict, include_reasoning: bool = False) -> str:
    parts: List[str] = []
    content = _text_value(message.get("content"))
    if content.strip():
        parts.append(content)
    if include_reasoning:
        reasoning = _text_value(message.get("reasoning_content"))
        if reasoning.strip():
            parts.append(f"[reasoning]\n{reasoning}")
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        parts.append(
            f"[tool_call] {function.get('name') or ''}"
            f"({function.get('arguments') or ''})"
        )
    if message.get("tool_call_id"):
        parts.append(f"[tool_call_id] {message['tool_call_id']}")
    return "\n".join(parts) if parts else "(空)"


def render_transcript(
    messages: List[dict],
    include_system: bool = True,
    include_reasoning: bool = False,
) -> str:
    """把消息列表渲染成人类可读文本,供摘要输入和压缩预览面板使用。"""
    blocks: List[str] = []
    for index, message in enumerate(messages, 1):
        role = message.get("role") or "unknown"
        if role == "system" and not include_system:
            continue
        blocks.append(f"### [{index}] {role}")
        blocks.append(_render_message_body(message, include_reasoning))
        blocks.append("")
    return "\n".join(blocks).strip()


def build_archive_note(archive_id: str, created_at: datetime) -> str:
    return (
        f"此前上下文已于 {created_at:%Y-%m-%d %H:%M:%S} 完成压缩，"
        f"原始上下文保存在编号为 {archive_id} 的归档文件中。"
        "如需查找历史信息，请使用 recallContext 工具。"
    )


def limit_summary(
    summary: str, archive_id: str, max_tokens: int = COMPACT_MAX_TOKENS
) -> str:
    """把摘要控制在合理长度,避免压缩后又立刻接近上下文上限。"""
    if estimate_text_tokens(summary) <= max_tokens:
        return summary
    note = (
        f"\n\n(摘要过长，已截断以控制上下文长度；"
        f"完整原始内容见归档 {archive_id}，可使用 recallContext 检索。)"
    )
    budget = max(500, max_tokens - estimate_text_tokens(note))
    ratio = budget / max(1, estimate_text_tokens(summary))
    keep = max(500, int(len(summary) * ratio))
    while keep > 500 and estimate_text_tokens(summary[:keep] + note) > max_tokens:
        keep = int(keep * 0.9)
    return summary[:keep].rstrip() + note


class ContextStore:
    """负责上下文预算、归档文件读写和历史检索。"""

    def __init__(
        self,
        root: Optional[Path] = None,
        model: str = "",
        context_window: Optional[int] = None,
        context_dir: str = str(CONTEXT_DIR),
        compact_threshold: float = COMPACT_THRESHOLD,
        compact_target_tokens: int = COMPACT_TARGET_TOKENS,
        compact_max_tokens: int = COMPACT_MAX_TOKENS,
        recall_max_matches: int = MAX_RECALL_MATCHES,
        recall_max_chars: int = MAX_RECALL_CHARS,
        recall_snippet_chars: int = MAX_RECALL_SNIPPET,
    ):
        project_root = Path(root or Path.cwd()).expanduser().resolve()
        directory = Path(context_dir)
        self.root = directory if directory.is_absolute() else project_root / directory
        self.window, self.default_window = resolve_context_window(
            model, context_window
        )
        self.compact_threshold = compact_threshold
        self.compact_target_tokens = compact_target_tokens
        self.compact_max_tokens = compact_max_tokens
        self.recall_max_matches = recall_max_matches
        self.recall_max_chars = recall_max_chars
        self.recall_snippet_chars = recall_snippet_chars
        self._base_tokens = 0
        self._base_index = 0

    @property
    def threshold(self) -> int:
        return int(self.window * self.compact_threshold)

    def reset_usage(self) -> None:
        self._base_tokens = 0
        self._base_index = 0

    def note_usage(self, total_tokens: Optional[int], history_length: int) -> None:
        """记录模型 API 返回的 usage,作为后续 Token 估算的基准。"""
        if total_tokens and total_tokens > 0:
            self._base_tokens = int(total_tokens)
            self._base_index = history_length

    def usage(self, messages: List[dict], tools: Optional[List[dict]] = None) -> ContextUsage:
        if self._base_tokens:
            tokens = self._base_tokens + estimate_messages_tokens(
                messages[self._base_index :]
            )
        else:
            tokens = estimate_messages_tokens(messages) + estimate_tools_tokens(
                tools or []
            )
        percent = min(100.0, tokens / max(1, self.window) * 100.0)
        return ContextUsage(tokens, self.window, percent, self.default_window)

    def new_archive(self) -> Archive:
        self.root.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        base_id = now.strftime("%Y%m%d-%H%M%S")
        archive_id = base_id
        suffix = 1
        while (self.root / f"{archive_id}.jsonl").exists():
            archive_id = f"{base_id}-{suffix}"
            suffix += 1
        return Archive(archive_id, self.root / f"{archive_id}.jsonl", now)

    def write_archive(self, archive: Archive, messages: List[dict]) -> None:
        """完整写入 JSONL;成功后才允许继续压缩,写入失败会抛出 OSError。"""
        self.root.mkdir(parents=True, exist_ok=True)
        temp_path = archive.path.parent / f"{archive.id}.jsonl.tmp"
        try:
            with temp_path.open("w", encoding="utf-8", newline="\n") as fp:
                for message in messages:
                    fp.write(json.dumps(message, ensure_ascii=False) + "\n")
                fp.flush()
                os.fsync(fp.fileno())
            temp_path.replace(archive.path)
        except OSError:
            try:
                temp_path.unlink()
            except OSError:
                pass
            raise

    def archive_paths(self) -> List[Path]:
        if not self.root.is_dir():
            return []
        try:
            paths = [p for p in self.root.glob("*.jsonl") if p.is_file()]
        except OSError:
            return []
        return sorted(paths, key=lambda path: path.name, reverse=True)

    def _resolve_archive(self, archive_id: str) -> Optional[Path]:
        raw = str(archive_id or "").strip()
        if raw.endswith(".jsonl"):
            raw = raw[: -len(".jsonl")]
        if not ARCHIVE_ID_PATTERN.fullmatch(raw):
            return None
        path = self.root / f"{raw}.jsonl"
        if not path.is_file():
            return None
        return path

    def recall(self, text: str, archive_id: Optional[str] = None) -> str:
        """在指定或全部归档中做全文关键词检索,返回片段、归档编号和位置。"""
        keyword = (text or "").strip()
        if not keyword:
            return "参数错误: 缺少必填参数 text。"

        if archive_id:
            path = self._resolve_archive(str(archive_id))
            if path is None:
                return f"错误: 归档编号 {archive_id!r} 不存在或格式不合法。"
            paths = [path]
            scope = f"在归档 {path.stem} 中"
        else:
            paths = self.archive_paths()
            if not paths:
                return "未找到任何上下文归档，当前没有可检索的历史记录。"
            scope = "在所有历史归档中"

        needle = keyword.casefold()
        matches: List[Tuple[str, int, str, str]] = []
        read_errors: List[str] = []
        total_matches = 0
        for path in paths:
            try:
                with path.open("r", encoding="utf-8", errors="replace") as fp:
                    for line_number, line in enumerate(fp, 1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            message = json.loads(line)
                        except ValueError:
                            message = {"role": "unknown", "content": line}
                        if not isinstance(message, dict):
                            message = {"role": "unknown", "content": str(message)}
                        if message.get("role") == "system":
                            continue
                        body = _render_message_body(message, include_reasoning=True)
                        position = body.casefold().find(needle)
                        if position < 0:
                            continue
                        total_matches += 1
                        if len(matches) >= self.recall_max_matches:
                            continue
                        start = max(0, position - 200)
                        end = min(len(body), position + len(keyword) + 300)
                        snippet = body[start:end]
                        if start > 0:
                            snippet = "..." + snippet
                        if end < len(body):
                            snippet = snippet + "..."
                        if len(snippet) > self.recall_snippet_chars:
                            snippet = snippet[: self.recall_snippet_chars] + "..."
                        role = message.get("role") or "unknown"
                        matches.append((path.stem, line_number, role, snippet))
            except OSError as exc:
                read_errors.append(f"归档 {path.stem} 读取失败: {exc}")

        if not matches:
            if read_errors:
                return "检索未找到匹配，且部分归档读取失败:\n" + "\n".join(read_errors)
            return f"{scope}未找到包含 {keyword!r} 的记录。"

        lines = [f"{scope}检索 {keyword!r}：共找到 {total_matches} 条匹配。"]
        if total_matches > len(matches):
            lines.append(f"匹配较多，仅返回前 {len(matches)} 条。")
        used_chars = 0
        for archive_name, line_number, role, snippet in matches:
            section = (
                f"\n### 归档 {archive_name} · 第 {line_number} 条 · {role}\n"
                f"{snippet}"
            )
            if used_chars + len(section) > self.recall_max_chars:
                lines.append("\n(结果过长，后续匹配已省略。)")
                break
            lines.append(section)
            used_chars += len(section)
        return "\n".join(lines)
