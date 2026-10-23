"""内置演示工具: getDate / isLeapYear(从 Practice02/chat3.py 迁移)。"""

import locale
import os
import subprocess

from .base import ToolRegistry, ToolSpec, make_handler, parse_arguments


def run_date_command() -> str:
    """调用本地 date 命令获取日期和时间。"""
    if os.name == "nt":
        command = 'cmd /u /c "date /t & time /t"'
        encoding = "utf-16-le"
    else:
        command = "date"
        encoding = locale.getpreferredencoding(False) or "utf-8"
    try:
        result = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"执行本地 date 命令失败: {exc}"

    stdout = (result.stdout or b"").decode(encoding, errors="replace")
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if lines:
        return " ".join(lines)

    stderr = (result.stderr or b"").decode(encoding, errors="replace").strip()
    if result.returncode != 0:
        return f"date 命令执行失败 (退出码 {result.returncode}): {stderr or '无输出'}"
    return stderr or "date 命令没有输出"


def _is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def check_leap_year(year: int) -> str:
    if _is_leap_year(year):
        return f"{year}年是闰年。"
    return f"{year}年不是闰年。"


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="getDate",
            description="获取当前电脑的日期和时间。通过调用本地 date 命令获取,返回当前日期和时间字符串。",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=make_handler(run_date_command),
        )
    )

    def _leap_handler(arguments: str) -> str:
        args = parse_arguments(arguments)
        if args is None:
            return "参数解析失败: arguments 不是合法的 JSON 对象。"
        if args.get("year") is None:
            return "参数错误: 缺少必填参数 year。"
        try:
            year = int(args["year"])
        except (TypeError, ValueError):
            return f"参数错误: year 必须是整数,收到 {args['year']!r}。"
        return check_leap_year(year)

    registry.register(
        ToolSpec(
            name="isLeapYear",
            description="判断指定年份是否是闰年。用 Python 代码计算,返回该年份是否为闰年的结论。",
            parameters={
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "要判断的年份,例如 2024",
                    }
                },
                "required": ["year"],
            },
            handler=_leap_handler,
        )
    )
