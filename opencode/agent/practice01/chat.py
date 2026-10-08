import configparser
import json
import os
import sys
from pathlib import Path

import requests

CONFIG_FILE = Path(__file__).resolve().with_name("config.ini")
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
TIMEOUT = 60

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


def iter_reply(resp):
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
            yield content


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

    while True:
        user_prompt = read_prompt()
        if user_prompt is None:
            return 1
        if not user_prompt:
            print("错误: 提示词为空,程序退出。")
            return 1

        history.append({"role": "user", "content": user_prompt})

        resp = None
        started = False
        reply_parts = []

        def fail(msg: str) -> int:
            if started:
                print()
            print(msg)
            return 1

        try:
            resp = open_stream(api_key, base_url, model, history)
            print("---", flush=True)

            chunks = 0
            for chunk in iter_reply(resp):
                print(chunk, end="", flush=True)
                reply_parts.append(chunk)
                chunks += 1
                started = True
            if chunks == 0:
                return fail("错误: 模型返回了空回复。")
            print()
            history.append({"role": "assistant", "content": "".join(reply_parts)})
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


if __name__ == "__main__":
    sys.exit(main())
