"""本地文件操作工具组(10 个,纯 Python 标准库实现,跨平台)。

与 Practice02/chat3.py 行为一致;`getToolsDirectory` 指向 sAgent 项目根目录。
"""

import locale
import mimetypes
import shutil
from pathlib import Path

from .base import ToolRegistry, ToolSpec, make_handler

MAX_READ_CHARS = 20000
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_text_file(path: Path):
    """读取纯文本;返回 (text, None) 或 (None, 错误文案)。"""
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
    return str(PROJECT_ROOT)


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
        return text[:MAX_READ_CHARS] + f"\n...(内容过长已截断,文件共 {len(text)} 字符)"
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
    if resolved == PROJECT_ROOT or resolved == PROJECT_ROOT.parent:
        return f"错误: 不允许删除 sAgent 自身目录: {resolved}"
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


_SPECS = [
    (
        "getToolsDirectory",
        "获取当前工具(sAgent)项目根目录的绝对路径。无参数。",
        {"type": "object", "properties": {}, "required": []},
        get_tools_directory,
        (),
        (),
    ),
    (
        "listDirectory",
        "列出指定目录下的所有文件和子目录。返回每个条目的类型([目录]/[文件])、名称,文件附带字节大小。",
        {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "要列出内容的目录路径"}},
            "required": ["path"],
        },
        list_directory,
        ("path",),
        (),
    ),
    (
        "getFileType",
        "获取指定文件的文件类型信息:是文件还是目录、扩展名、MIME 类型和字节大小。",
        {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "文件或目录的路径"}},
            "required": ["path"],
        },
        get_file_type,
        ("path",),
        (),
    ),
    (
        "readFile",
        "获取指定文件的内容,仅支持纯文本格式文件。返回文件的文本内容(过长时截断)。",
        {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "要读取的纯文本文件路径"}},
            "required": ["path"],
        },
        read_text_file,
        ("path",),
        (),
    ),
    (
        "createFile",
        "根据指定的目录和文件名创建新文件,同时支持创建新目录(目录不存在时自动逐级创建)。可选写入初始内容。",
        {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "新文件所在目录,不存在时会自动创建",
                },
                "filename": {"type": "string", "description": "新文件的文件名,例如 note.txt"},
                "content": {"type": "string", "description": "写入文件的初始内容,默认为空字符串"},
            },
            "required": ["directory", "filename"],
        },
        create_text_file,
        ("directory", "filename"),
        ("content",),
    ),
    (
        "editFile",
        "编辑指定文件的内容,仅支持纯文本格式文件。mode 取值: write=用 content 覆盖整个文件; append=在文件末尾追加 content; replace=把文件中所有 old_text 替换为 new_text。",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "要编辑的纯文本文件路径"},
                "mode": {
                    "type": "string",
                    "enum": ["write", "append", "replace"],
                    "description": "编辑模式: write 覆盖写入 / append 追加 / replace 查找替换",
                },
                "content": {"type": "string", "description": "write 和 append 模式下要写入的内容"},
                "old_text": {"type": "string", "description": "replace 模式下要被替换的原文本"},
                "new_text": {"type": "string", "description": "replace 模式下替换后的新文本"},
            },
            "required": ["path", "mode"],
        },
        edit_text_file,
        ("path", "mode"),
        ("content", "old_text", "new_text"),
    ),
    (
        "createDirectory",
        "创建新目录,支持同时创建尚不存在的上级目录。目录已存在时不报错。",
        {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "要创建的目录路径"}},
            "required": ["path"],
        },
        create_directory,
        ("path",),
        (),
    ),
    (
        "deleteDirectory",
        "删除指定目录及其全部内容(支持删除非空目录)。删除后不可恢复,请谨慎调用。",
        {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "要删除的目录路径"}},
            "required": ["path"],
        },
        delete_directory,
        ("path",),
        (),
    ),
    (
        "deleteFile",
        "删除指定的文件。删除后不可恢复,请谨慎调用。",
        {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "要删除的文件路径"}},
            "required": ["path"],
        },
        delete_file,
        ("path",),
        (),
    ),
    (
        "renameItem",
        "重命名或移动文件和目录:把 old_path 重命名为 new_path(可跨目录移动)。",
        {
            "type": "object",
            "properties": {
                "old_path": {"type": "string", "description": "原文件或目录路径"},
                "new_path": {
                    "type": "string",
                    "description": "重命名后的文件或目录路径(可包含新的目录位置)",
                },
            },
            "required": ["old_path", "new_path"],
        },
        rename_item,
        ("old_path", "new_path"),
        (),
    ),
]


def register(registry: ToolRegistry) -> None:
    for name, description, parameters, func, required, optional in _SPECS:
        registry.register(
            ToolSpec(
                name=name,
                description=description,
                parameters=parameters,
                handler=make_handler(func, required=required, optional=optional),
            )
        )
