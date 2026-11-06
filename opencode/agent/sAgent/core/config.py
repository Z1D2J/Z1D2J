"""配置加载(基础设施层,被 core.agent 依赖,不依赖任何 UI)。

所有可调参数都集中在这里: config.ini 优先,环境变量作为兜底,
未配置时使用本文件中的默认值。配置文件不存在时会自动生成一份带 mock
信息的完整配置,并由 TUI 提示用户修改后重启。
"""

import configparser
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .errors import ConfigError

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TIMEOUT = 60
DEFAULT_MAX_TOOL_ROUNDS = 10

MOCK_API_KEY = "sk-mock-please-replace-me"
MOCK_BASE_URL = "https://api.example.com/v1"
MOCK_MODEL = "mock-model"
MOCK_SEARCH_KEY = "mock-search-key"

SEARCH_KEY_OPTION = "baidu_qianfan_api_key"


@dataclass(frozen=True)
class Settings:
    # [api]
    api_key: str
    base_url: str
    model: str
    timeout: int = DEFAULT_TIMEOUT
    connect_timeout: int = 10
    max_tool_rounds: int = DEFAULT_MAX_TOOL_ROUNDS
    context_window: Optional[int] = None
    include_usage: bool = True
    # [context]
    context_dir: str = ".agents/context"
    compact_threshold: float = 0.60
    compact_target_tokens: int = 5000
    compact_max_tokens: int = 6500
    recall_max_matches: int = 8
    recall_max_chars: int = 8000
    recall_snippet_chars: int = 600
    # [skills]
    skills_extra_dirs: str = ""
    # [session]
    session_dir: str = ".agents/sessions"
    auto_save_sessions: bool = True
    agents_file: str = "AGENTS.md"
    agents_max_chars: int = 20000
    # [mcp]
    mcp_config_file: str = ".mcp.json"
    mcp_connect_timeout: float = 20.0
    mcp_call_timeout: float = 120.0
    mcp_max_tool_name_length: int = 64
    mcp_max_result_chars: int = 30000
    # [tools]
    file_read_max_chars: int = 20000
    run_cli_timeout: int = 30
    run_cli_max_timeout: int = 300
    run_cli_max_output_chars: int = 4000
    office_timeout: int = 60
    office_max_timeout: int = 300
    office_max_output_chars: int = 8000
    web_fetch_timeout: int = 60
    web_fetch_connect_timeout: int = 15
    web_fetch_max_chars: int = 30000
    web_search_timeout: int = 30
    web_search_top_k: int = 8
    web_search_max_top_k: int = 20
    web_search_query_max_chars: int = 72
    web_search_snippet_max_chars: int = 300
    web_search_result_max_chars: int = 12000
    # [tui]
    transcript_max_lines: int = 2000
    thinking_visible: bool = True
    # [search]
    search_api_key: str = ""
    # 运行期信息
    config_file: str = ""
    config_created: bool = False


def default_config_path() -> Path:
    configured = os.environ.get("SAGENT_CONFIG", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.cwd() / "config.ini"


CONFIG_FILE = default_config_path()


def _get(
    config: configparser.ConfigParser,
    section: str,
    option: str,
    env: str = "",
    default: str = "",
) -> str:
    if config.has_option(section, option):
        value = config.get(section, option).strip()
        if value:
            return value
    if env:
        value = os.environ.get(env, "").strip()
        if value:
            return value
    return default


def _get_int(
    config: configparser.ConfigParser,
    section: str,
    option: str,
    default: int,
    env: str = "",
) -> int:
    raw = _get(config, section, option, env, "")
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _get_float(
    config: configparser.ConfigParser,
    section: str,
    option: str,
    default: float,
    env: str = "",
) -> float:
    raw = _get(config, section, option, env, "")
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


def _get_bool(
    config: configparser.ConfigParser,
    section: str,
    option: str,
    default: bool = True,
    env: str = "",
) -> bool:
    raw = _get(config, section, option, env, "")
    if not raw:
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off")


def _parse_window_size(raw: str) -> Optional[int]:
    """支持 "128k"、"1m" 或纯数字(单位: token)。"""
    text = (raw or "").strip().lower()
    if not text:
        return None
    try:
        if text.endswith("k"):
            value = int(float(text[:-1]) * 1024)
        elif text.endswith("m"):
            value = int(float(text[:-1]) * 1024 * 1024)
        else:
            value = int(text)
    except ValueError:
        return None
    return value if value > 0 else None


def _config_text() -> str:
    return f"""; sAgent 配置文件
; 首次生成时使用 mock 值,请修改 [api] 段的 key / base_url / model 后重新启动。
; 所有未填写的参数都会使用程序内置默认值。

[api]
key = {MOCK_API_KEY}
base_url = {MOCK_BASE_URL}
model = {MOCK_MODEL}
timeout = {DEFAULT_TIMEOUT}
connect_timeout = 10
max_tool_rounds = {DEFAULT_MAX_TOOL_ROUNDS}
; 上下文窗口大小,支持 128k / 1m / 纯数字(token);留空则自动判断,无法判断默认 128k
context_window =
; 是否向接口请求 Token usage;接口不支持时可设为 false
stream_usage = true

[context]
dir = .agents/context
compact_threshold = 0.60
compact_target_tokens = 5000
compact_max_tokens = 6500
recall_max_matches = 8
recall_max_chars = 8000
recall_snippet_chars = 600

[skills]
; 额外 Skill 目录(逗号分隔),用于加载项目 .agents/skills 之外的 Skill
; 例如: D:\\path\\to\\office\\.agents\\skills
extra_dirs =

[session]
dir = .agents/sessions
; 每轮结束后自动保存会话
auto_save = true
agents_file = AGENTS.md
agents_max_chars = 20000

[mcp]
config_file = .mcp.json
connect_timeout = 20
call_timeout = 120
max_tool_name_length = 64
max_result_chars = 30000

[tools]
file_read_max_chars = 20000
run_cli_default_timeout = 30
run_cli_max_timeout = 300
run_cli_max_output_chars = 4000
office_default_timeout = 60
office_max_timeout = 300
office_max_output_chars = 8000
web_fetch_timeout = 60
web_fetch_connect_timeout = 15
web_fetch_max_chars = 30000
web_search_timeout = 30
web_search_top_k = 8
web_search_max_top_k = 20
web_search_query_max_chars = 72
web_search_snippet_max_chars = 300
web_search_result_max_chars = 12000

[tui]
transcript_max_lines = 2000
thinking_visible = true

[search]
baidu_qianfan_api_key = {MOCK_SEARCH_KEY}
"""


def _write_default_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_config_text(), encoding="utf-8")


def _build_settings(
    config: configparser.ConfigParser, path: Path, created: bool
) -> Settings:
    api_key = _get(
        config, "api", "key", "CHAT_API_KEY", MOCK_API_KEY if created else ""
    )
    if not api_key:
        raise ConfigError(
            f"未找到 API Key,请在 {path} 中设置 [api] key。\n"
            "示例:\n[api]\nkey = sk-xxxx"
        )

    return Settings(
        api_key=api_key,
        base_url=_get(
            config, "api", "base_url", "CHAT_BASE_URL", DEFAULT_BASE_URL
        ).rstrip("/"),
        model=_get(config, "api", "model", "CHAT_MODEL", DEFAULT_MODEL),
        timeout=_get_int(config, "api", "timeout", DEFAULT_TIMEOUT, "CHAT_TIMEOUT"),
        connect_timeout=_get_int(config, "api", "connect_timeout", 10),
        max_tool_rounds=_get_int(
            config, "api", "max_tool_rounds", DEFAULT_MAX_TOOL_ROUNDS
        ),
        context_window=_parse_window_size(
            _get(config, "api", "context_window", "CHAT_CONTEXT_WINDOW", "")
        ),
        include_usage=_get_bool(
            config, "api", "stream_usage", True, "CHAT_STREAM_USAGE"
        ),
        context_dir=_get(config, "context", "dir", "", ".agents/context"),
        compact_threshold=_get_float(
            config, "context", "compact_threshold", 0.60
        ),
        compact_target_tokens=_get_int(
            config, "context", "compact_target_tokens", 5000
        ),
        compact_max_tokens=_get_int(
            config, "context", "compact_max_tokens", 6500
        ),
        recall_max_matches=_get_int(config, "context", "recall_max_matches", 8),
        recall_max_chars=_get_int(config, "context", "recall_max_chars", 8000),
        recall_snippet_chars=_get_int(
            config, "context", "recall_snippet_chars", 600
        ),
        skills_extra_dirs=_get(config, "skills", "extra_dirs", "", ""),
        session_dir=_get(config, "session", "dir", "", ".agents/sessions"),
        auto_save_sessions=_get_bool(config, "session", "auto_save", True),
        agents_file=_get(config, "session", "agents_file", "", "AGENTS.md"),
        agents_max_chars=_get_int(config, "session", "agents_max_chars", 20000),
        mcp_config_file=_get(config, "mcp", "config_file", "", ".mcp.json"),
        mcp_connect_timeout=_get_float(
            config, "mcp", "connect_timeout", 20.0
        ),
        mcp_call_timeout=_get_float(config, "mcp", "call_timeout", 120.0),
        mcp_max_tool_name_length=_get_int(
            config, "mcp", "max_tool_name_length", 64
        ),
        mcp_max_result_chars=_get_int(config, "mcp", "max_result_chars", 30000),
        file_read_max_chars=_get_int(
            config, "tools", "file_read_max_chars", 20000
        ),
        run_cli_timeout=_get_int(config, "tools", "run_cli_default_timeout", 30),
        run_cli_max_timeout=_get_int(
            config, "tools", "run_cli_max_timeout", 300
        ),
        run_cli_max_output_chars=_get_int(
            config, "tools", "run_cli_max_output_chars", 4000
        ),
        office_timeout=_get_int(config, "tools", "office_default_timeout", 60),
        office_max_timeout=_get_int(config, "tools", "office_max_timeout", 300),
        office_max_output_chars=_get_int(
            config, "tools", "office_max_output_chars", 8000
        ),
        web_fetch_timeout=_get_int(
            config, "tools", "web_fetch_timeout", 60
        ),
        web_fetch_connect_timeout=_get_int(
            config, "tools", "web_fetch_connect_timeout", 15
        ),
        web_fetch_max_chars=_get_int(
            config, "tools", "web_fetch_max_chars", 30000
        ),
        web_search_timeout=_get_int(
            config, "tools", "web_search_timeout", 30
        ),
        web_search_top_k=_get_int(config, "tools", "web_search_top_k", 8),
        web_search_max_top_k=_get_int(
            config, "tools", "web_search_max_top_k", 20
        ),
        web_search_query_max_chars=_get_int(
            config, "tools", "web_search_query_max_chars", 72
        ),
        web_search_snippet_max_chars=_get_int(
            config, "tools", "web_search_snippet_max_chars", 300
        ),
        web_search_result_max_chars=_get_int(
            config, "tools", "web_search_result_max_chars", 12000
        ),
        transcript_max_lines=_get_int(
            config, "tui", "transcript_max_lines", 2000
        ),
        thinking_visible=_get_bool(config, "tui", "thinking_visible", True),
        search_api_key=_get(
            config, "search", SEARCH_KEY_OPTION, "BAIDU_QIANFAN_API_KEY", ""
        ),
        config_file=str(path),
        config_created=created,
    )


def load_config(config_file: Optional[Path] = None) -> Settings:
    path = Path(config_file) if config_file is not None else default_config_path()
    path = path.expanduser()

    created = False
    if not path.is_file():
        try:
            _write_default_config(path)
        except OSError as exc:
            raise ConfigError(f"创建默认配置文件失败: {path} ({exc})") from exc
        created = True

    config = configparser.ConfigParser()
    try:
        config.read(path, encoding="utf-8-sig")
    except configparser.Error as exc:
        raise ConfigError(f"config.ini 解析失败: {exc}") from exc

    return _build_settings(config, path, created)


def load_search_api_key(config_file: Optional[Path] = None) -> str:
    """兼容旧接口;新代码优先使用 Settings.search_api_key。"""
    path = Path(config_file) if config_file is not None else default_config_path()
    config = configparser.ConfigParser()
    if path.is_file():
        try:
            config.read(path, encoding="utf-8-sig")
        except configparser.Error:
            return ""
    return _get(config, "search", SEARCH_KEY_OPTION, "BAIDU_QIANFAN_API_KEY", "")
