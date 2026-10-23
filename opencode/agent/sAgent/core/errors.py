"""sAgent 错误类型(核心层,UI 无关)。"""


class ConfigError(Exception):
    """配置缺失或解析失败。"""


class AgentError(Exception):
    """Agent 运行期错误,message 为可直接展示给用户的中文文案。"""
