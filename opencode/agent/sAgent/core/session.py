"""会话持久化: 把聊天历史保存为可恢复的 JSONL 事件日志。

文件格式(每行一个 JSON 对象):
- {"type": "meta", "id", "created_at", "updated_at", "title"}
- {"type": "message", "timestamp", "message": {...}}  # 原样保存聊天消息

保存时整份快照原子写入;恢复时按行读取 message 事件,保持原始顺序。
"""

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

SESSION_DIR = Path(".agents") / "sessions"
SESSION_ID_PATTERN = re.compile(r"^\d{8}-\d{6}(?:-\d+)?$")
TITLE_MAX_CHARS = 60
AGENTS_MARKER = "【项目上下文：AGENTS.md】"


@dataclass(frozen=True)
class SessionInfo:
    id: str
    created_at: str
    updated_at: str
    title: str
    message_count: int
    path: Path


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _title_from_messages(messages: List[dict]) -> str:
    for message in messages:
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        text = " ".join(content.split())
        if not text or text.startswith(AGENTS_MARKER):
            continue
        return text[:TITLE_MAX_CHARS]
    return "新会话"


class SessionStore:
    def __init__(self, root: Optional[Path] = None, directory: str = str(SESSION_DIR)):
        project_root = Path(root or Path.cwd()).expanduser().resolve()
        folder = Path(directory)
        self.root = folder if folder.is_absolute() else project_root / folder

    def new_id(self) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        base_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        session_id = base_id
        suffix = 1
        while (self.root / f"{session_id}.jsonl").exists():
            session_id = f"{base_id}-{suffix}"
            suffix += 1
        return session_id

    def _path(self, session_id: str) -> Optional[Path]:
        raw = str(session_id or "").strip()
        if raw.endswith(".jsonl"):
            raw = raw[: -len(".jsonl")]
        if not SESSION_ID_PATTERN.fullmatch(raw):
            return None
        return self.root / f"{raw}.jsonl"

    def save(
        self, session_id: str, created_at: str, messages: List[dict]
    ) -> SessionInfo:
        path = self._path(session_id)
        if path is None:
            raise OSError(f"会话编号不合法: {session_id!r}")
        self.root.mkdir(parents=True, exist_ok=True)
        now = _now_text()
        title = self._existing_title(path) or _title_from_messages(messages)
        temp_path = path.parent / f"{path.stem}.jsonl.tmp"

        try:
            with temp_path.open("w", encoding="utf-8", newline="\n") as fp:
                meta = {
                    "type": "meta",
                    "id": session_id,
                    "created_at": created_at,
                    "updated_at": now,
                    "title": title,
                }
                fp.write(json.dumps(meta, ensure_ascii=False) + "\n")
                for message in messages:
                    event = {
                        "type": "message",
                        "timestamp": now,
                        "message": message,
                    }
                    fp.write(json.dumps(event, ensure_ascii=False) + "\n")
                fp.flush()
                os.fsync(fp.fileno())
            temp_path.replace(path)
        except OSError:
            try:
                temp_path.unlink()
            except OSError:
                pass
            raise

        return SessionInfo(
            id=session_id,
            created_at=created_at,
            updated_at=now,
            title=title,
            message_count=len(messages),
            path=path,
        )

    @staticmethod
    def _existing_title(path: Path) -> str:
        try:
            with path.open("r", encoding="utf-8", errors="replace") as fp:
                first_line = fp.readline().strip()
        except OSError:
            return ""
        try:
            meta = json.loads(first_line) if first_line else {}
        except ValueError:
            return ""
        if not isinstance(meta, dict) or meta.get("type") != "meta":
            return ""
        title = meta.get("title")
        return title if isinstance(title, str) else ""

    def _read_meta_and_messages(
        self, path: Path
    ) -> Tuple[Optional[dict], List[dict]]:
        meta: Optional[dict] = None
        messages: List[dict] = []
        with path.open("r", encoding="utf-8", errors="replace") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(event, dict):
                    continue
                if event.get("type") == "meta" and meta is None:
                    meta = event
                elif event.get("type") == "message":
                    message = event.get("message")
                    if isinstance(message, dict):
                        messages.append(message)
        return meta, messages

    def load(self, session_id: str) -> Tuple[SessionInfo, List[dict]]:
        path = self._path(session_id)
        if path is None or not path.is_file():
            raise OSError(f"会话不存在或编号不合法: {session_id}")
        try:
            meta, messages = self._read_meta_and_messages(path)
        except OSError as exc:
            raise OSError(f"读取会话失败: {exc}") from exc

        meta = meta or {}
        session_id = str(meta.get("id") or path.stem)
        created_at = str(meta.get("created_at") or "")
        updated_at = str(meta.get("updated_at") or "")
        title = str(meta.get("title") or _title_from_messages(messages))
        info = SessionInfo(
            id=session_id,
            created_at=created_at,
            updated_at=updated_at,
            title=title,
            message_count=len(messages),
            path=path,
        )
        return info, messages

    def list_sessions(self) -> List[SessionInfo]:
        if not self.root.is_dir():
            return []
        try:
            paths = [p for p in self.root.glob("*.jsonl") if p.is_file()]
        except OSError:
            return []

        sessions: List[SessionInfo] = []
        for path in paths:
            try:
                meta, messages = self._read_meta_and_messages(path)
            except OSError:
                continue
            meta = meta or {}
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            except OSError:
                mtime = ""
            sessions.append(
                SessionInfo(
                    id=str(meta.get("id") or path.stem),
                    created_at=str(meta.get("created_at") or mtime),
                    updated_at=str(meta.get("updated_at") or mtime),
                    title=str(meta.get("title") or _title_from_messages(messages)),
                    message_count=len(messages),
                    path=path,
                )
            )
        return sorted(
            sessions,
            key=lambda info: (info.updated_at, info.id),
            reverse=True,
        )
