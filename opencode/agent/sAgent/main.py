"""sAgent 统一入口。

用法:
    python main.py               # 默认 TUI 界面
    python main.py --ui tui      # 显式指定界面
    python main.py --ui web      # 预留: Web 界面(尚未实现)

UI 后端通过 UI_BACKENDS 注册表扩展: 新增界面时只需注册一个工厂,
不改动 core 与本文件之外的调度逻辑。
"""

import argparse
import sys
from typing import Callable

from core import Agent, ConfigError


def _launch_tui(agent: Agent) -> int:
    from tui.app import sAgentApp

    sAgentApp(agent).run()
    return 0


UI_BACKENDS: dict = {
    "tui": _launch_tui,
    # "web": _launch_web,     # 预留: 事件契约已就绪,接入 ASGI/长连接即可
    # "desktop": _launch_desktop,  # 预留: 同一事件流接 pywebview/Tauri
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="sAgent 智能助手")
    parser.add_argument(
        "--ui",
        default="tui",
        choices=sorted(UI_BACKENDS) + ["web", "desktop"],
        help="界面后端(默认 tui)",
    )
    args = parser.parse_args(argv)

    try:
        agent = Agent()
    except ConfigError as exc:
        print(f"配置错误: {exc}", file=sys.stderr)
        return 1

    factory = UI_BACKENDS.get(args.ui)
    if factory is None:
        print(
            f"界面 '{args.ui}' 尚未实现。当前可用: {', '.join(sorted(UI_BACKENDS))}。",
            file=sys.stderr,
        )
        agent.close()
        return 2
    try:
        return factory(agent)
    finally:
        agent.close()


if __name__ == "__main__":
    sys.exit(main())
