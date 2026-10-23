"""配置加载(基础设施层,被 core.agent 依赖,不依赖任何 UI)。"""

import configparser
import os
from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigError

CONFIG_FILE = Path(__file__).resolve().parents[1] / "config.ini"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TIMEOUT = 60
DEFAULT_MAX_TOOL_ROUNDS = 10


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model: str
    timeout: int = DEFAULT_TIMEOUT
    max_tool_rounds: int = DEFAULT_MAX_TOOL_ROUNDS


def _pick(config: configparser.ConfigParser, option: str, env: str, default: str = "") -> str:
    if config.has_option("api", option):
        value = config.get("api", option).strip()
        if value:
            return value
    return os.environ.get(env, "").strip() or default


def load_config(config_file: Path = CONFIG_FILE) -> Settings:
    config = configparser.ConfigParser()
    if config_file.is_file():
        try:
            config.read(config_file, encoding="utf-8-sig")
        except configparser.Error as exc:
            raise ConfigError(f"config.ini 解析失败: {exc}") from exc

    api_key = _pick(config, "key", "CHAT_API_KEY")
    if not api_key:
        if not config_file.is_file():
            raise ConfigError(f"未找到配置文件 {config_file},请创建它并填写 api.key。")
        raise ConfigError(
            f"未找到 API Key,请在 {config_file} 中设置 api.key。\n"
            "示例:\n[api]\nkey = sk-xxxx"
        )

    return Settings(
        api_key=api_key,
        base_url=_pick(config, "base_url", "CHAT_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        model=_pick(config, "model", "CHAT_MODEL", DEFAULT_MODEL),
    )
