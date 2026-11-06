"""Agent Skills 动态加载: 发现项目根目录下的 .agents/skills/ 并维护技能目录。

发现阶段只解析每个 SKILL.md 的 YAML Frontmatter(name / description),不读取正文;
完整内容仅在 LLM 调用 loadSkill 工具时由 SkillCatalog.load 按需读取。
"""

import locale
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

SKILLS_DIR = Path(".agents") / "skills"
SKILL_FILE = "SKILL.md"
SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SKILL_NAME_MAX_LENGTH = 64


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    path: Path
    skill_file: Path


def _read_frontmatter(path: Path) -> Optional[dict]:
    """只读取文件开头 --- 包围的 YAML Frontmatter,不触碰正文。"""
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as fp:
            first = fp.readline()
            if first.strip() != "---":
                return None
            lines = []
            for line in fp:
                if line.strip() == "---":
                    break
                lines.append(line)
            else:
                return None
    except OSError:
        return None

    try:
        import yaml

        data = yaml.safe_load("".join(lines))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _clean_text(value) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())


def _normalize_skill_name(name) -> Optional[str]:
    """统一为小写字母/数字/连字符格式;不合法时返回 None。"""
    if not isinstance(name, str):
        return None
    candidate = re.sub(r"[\s_]+", "-", name.strip().casefold())
    candidate = re.sub(r"-+", "-", candidate).strip("-")
    if not candidate or len(candidate) > SKILL_NAME_MAX_LENGTH:
        return None
    if not SKILL_NAME_PATTERN.fullmatch(candidate):
        return None
    return candidate


def _split_frontmatter(content: str) -> Tuple[Optional[str], str]:
    """拆出 YAML Frontmatter 文本与正文;没有合法 Frontmatter 时返回 (None, 原文)。"""
    text = content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").lstrip("\n")
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, text
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1 :])
    return None, text


def _parse_frontmatter(header: str) -> Optional[dict]:
    try:
        import yaml

        data = yaml.safe_load(header)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _derive_description(body: str) -> str:
    """从正文首行提取简短 description,作为缺失时的兜底。"""
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("<!--"):
            continue
        line = re.sub(r"^#{1,6}\s*", "", line)
        cleaned = " ".join(line.split())
        if cleaned:
            return cleaned
    return ""


def _build_skill_content(name: str, context: str) -> Tuple[Optional[str], Optional[str]]:
    """规范化为带 name/description Frontmatter 的 SKILL.md 内容。"""
    header, body = _split_frontmatter(context)
    if header is None and context.lstrip("\ufeff").lstrip().startswith("---"):
        return None, "错误: skillContext 的 YAML Frontmatter 缺少结束标记 ---。"
    meta: dict = {}
    if header is not None:
        parsed = _parse_frontmatter(header)
        if parsed is None:
            return None, "错误: skillContext 的 YAML Frontmatter 无法解析,请提供合法的 YAML。"
        meta = parsed

    description = _clean_text(meta.get("description"))
    if not description:
        description = _clean_text(_derive_description(body))
    if not description:
        return None, "错误: skillContext 缺少 description,无法生成 Skill。"
    if not body.strip():
        return None, "错误: skillContext 缺少正文内容,无法生成 Skill。"

    frontmatter = {"name": name, "description": description}
    for key, value in meta.items():
        if key in ("name", "description") or value is None:
            continue
        frontmatter[key] = value

    try:
        import yaml

        header_text = yaml.safe_dump(
            frontmatter, allow_unicode=True, sort_keys=False
        ).strip()
    except Exception as exc:
        return None, f"错误: 生成 YAML Frontmatter 失败: {exc}"

    content = f"---\n{header_text}\n---\n\n{body.strip()}\n"
    return content, None


class SkillCatalog:
    """启动时扫描一次 Skill 元数据,并为 loadSkill 提供受控的文件读取。"""

    def __init__(
        self,
        root: Optional[Path] = None,
        project_root: Optional[Path] = None,
        extra_roots: Optional[Iterable[Path]] = None,
    ):
        self.project_root = Path(project_root or Path.cwd()).expanduser().resolve()
        self.root = Path(root).expanduser().resolve() if root else self.project_root / SKILLS_DIR
        self.extra_roots = [self._resolve_root(path) for path in (extra_roots or [])]
        self._skills: Dict[str, Skill] = {}
        self.discover()

    def _resolve_root(self, path: Path) -> Path:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = self.project_root / candidate
        return candidate.resolve()

    @property
    def roots(self) -> List[Path]:
        """按优先级返回全部 Skill 根目录(项目内目录优先,其余为额外目录)。"""
        ordered: List[Path] = []
        for root in [self.root, *self.extra_roots]:
            if root not in ordered:
                ordered.append(root)
        return ordered

    @property
    def skills(self) -> List[Skill]:
        return list(self._skills.values())

    def get(self, name: str) -> Optional[Skill]:
        skill = self._skills.get(name)
        if skill is not None:
            return skill
        lowered = name.casefold()
        for candidate in self._skills.values():
            if candidate.name.casefold() == lowered:
                return candidate
        return None

    def discover(self) -> None:
        self._skills.clear()
        for root in self.roots:
            self._discover_root(root)

    def _discover_root(self, root: Path) -> None:
        if not root.is_dir():
            return
        try:
            entries = sorted(root.iterdir(), key=lambda p: p.name.casefold())
        except OSError:
            return

        for entry in entries:
            if not entry.is_dir():
                continue
            skill_file = entry / SKILL_FILE
            if not skill_file.is_file():
                continue
            meta = _read_frontmatter(skill_file)
            if meta is None:
                continue
            name = _clean_text(meta.get("name"))
            description = _clean_text(meta.get("description"))
            if not name or not description:
                continue
            if name in self._skills:
                continue
            self._skills[name] = Skill(
                name=name,
                description=description,
                path=entry.resolve(),
                skill_file=skill_file.resolve(),
            )

    def prompt_section(self) -> str:
        if not self._skills:
            return ""
        lines = ["You have access to the following skills:"]
        for skill in self._skills.values():
            lines.append(f"- `{skill.name}`: {skill.description}")
        lines.append(
            "Use the `loadSkill` tool to load the full instructions of a skill when needed. "
            "You can also load additional files referenced by a skill."
        )
        return "\n".join(lines)

    def load(self, name, filename=None) -> str:
        skill = self.get(str(name).strip())
        if skill is None:
            available = ", ".join(s.name for s in self._skills.values()) or "(无)"
            return f"错误: 未找到名为 {name!r} 的 Skill。可用 Skill: {available}"

        if filename is None or (isinstance(filename, str) and not filename.strip()):
            return self._read_text(skill.skill_file)
        if not isinstance(filename, str):
            filename = str(filename)
        return self._load_attachment(skill, filename.strip())

    def create(self, name, context) -> str:
        """按 Agent Skills 规范在项目 skills 目录创建新 Skill,不覆盖已有内容。"""
        normalized = _normalize_skill_name(name)
        if normalized is None:
            return (
                f"错误: Skill 名称 {name!r} 不合法。"
                f"名称只能由小写字母、数字和连字符组成,最长 {SKILL_NAME_MAX_LENGTH} 个字符,"
                "例如 my-web-search。"
            )
        if not isinstance(context, str):
            context = str(context)

        target_dir = self.root / normalized
        existing = self.get(normalized)
        if target_dir.exists() or existing is not None:
            location = existing.path if existing is not None else target_dir
            return (
                f"错误: Skill {normalized!r} 已存在,未做任何修改。"
                f"位置: {location}。如需更新请先确认后再手动编辑。"
            )

        content, error = _build_skill_content(normalized, context)
        if error:
            return error

        self.root.mkdir(parents=True, exist_ok=True)
        target_dir.mkdir(parents=True, exist_ok=False)
        skill_file = target_dir / SKILL_FILE
        skill_file.write_text(content, encoding="utf-8")
        self.discover()
        return (
            f"已创建 Skill: {normalized}\n"
            f"目录: {target_dir}\n"
            f"文件: {skill_file}\n"
            "如需补充 references/、scripts/ 等辅助文件,请继续调用 fileOps 工具。"
        )


    def _load_attachment(self, skill: Skill, filename: str) -> str:
        raw = Path(filename).expanduser()

        if raw.is_absolute():
            target = self._within(skill.path, raw)
            if target is None:
                return f"错误: 附件路径超出 Skill 目录范围: {raw}"
            return self._read_attachment(skill, target)

        inside_seen = False
        for base in (skill.path, self.project_root):
            target = self._within(skill.path, base / raw)
            if target is None:
                continue
            inside_seen = True
            if target.exists():
                return self._read_attachment(skill, target)

        if len(raw.parts) == 1:
            matches = self._search_by_name(skill, raw.name)
            if len(matches) == 1:
                return self._read_text(matches[0])
            if len(matches) > 1:
                candidates = "\n".join(
                    f"- {path.relative_to(skill.path).as_posix()}" for path in matches
                )
                return (
                    f"错误: Skill {skill.name!r} 下存在多个名为 {raw.name!r} 的文件,"
                    f"请通过 filename 指定具体路径:\n{candidates}"
                )

        if not inside_seen:
            return f"错误: 附件路径超出 Skill 目录范围: {filename}"
        return f"错误: 未找到附件文件: {filename}"

    def _search_by_name(self, skill: Skill, name: str) -> List[Path]:
        matches: List[Path] = []
        seen = set()
        try:
            found = skill.path.rglob(name)
            for path in found:
                target = self._within(skill.path, path)
                if target is None or not target.is_file() or target in seen:
                    continue
                seen.add(target)
                matches.append(target)
        except OSError:
            return []
        return sorted(matches)

    def _read_attachment(self, skill: Skill, target: Path) -> str:
        guarded = self._within(skill.path, target)
        if guarded is None:
            return f"错误: 附件路径超出 Skill 目录范围: {target}"
        if not guarded.exists():
            return f"错误: 附件文件不存在: {target}"
        if not guarded.is_file():
            return f"错误: 路径不是文件: {target}"
        return self._read_text(guarded)

    @staticmethod
    def _within(base: Path, candidate: Path) -> Optional[Path]:
        """解析路径并确保结果仍位于 base 目录内部(防目录穿越与符号链接逃逸)。"""
        try:
            resolved_base = base.resolve()
            resolved = candidate.resolve()
        except OSError:
            return None
        try:
            resolved.relative_to(resolved_base)
        except ValueError:
            return None
        return resolved

    @staticmethod
    def _read_text(path: Path) -> str:
        try:
            data = path.read_bytes()
        except OSError as exc:
            return f"读取失败: {exc}"
        if b"\x00" in data:
            return "错误: 该文件疑似二进制文件,仅支持读取纯文本。"
        encodings = ["utf-8-sig", locale.getpreferredencoding(False) or "utf-8", "gbk"]
        for encoding in encodings:
            try:
                return data.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                continue
        return "错误: 文件解码失败,可能不是纯文本格式文件。"
