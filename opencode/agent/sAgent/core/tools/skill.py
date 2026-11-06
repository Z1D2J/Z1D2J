"""loadSkill 工具: 按需加载 Skill 的完整指令或 Skill 目录内的附件。"""

from ..skills import SkillCatalog
from .base import ToolRegistry, ToolSpec, make_handler


def register(registry: ToolRegistry, catalog: SkillCatalog) -> None:
    registry.register(
        ToolSpec(
            name="loadSkill",
            description=(
                "加载指定 Skill 的完整内容。只传 name 时读取该 Skill 的 SKILL.md 全文;"
                "同时传 filename 时读取 Skill 目录内的指定附件,不会重复加载 SKILL.md。"
                "filename 支持相对于 Skill 目录的路径、项目相对路径和绝对路径;"
                "只给文件名时会递归查找,若存在多个同名文件则返回候选路径。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "要加载的 Skill 名称"},
                    "filename": {
                        "type": "string",
                        "description": "可选,Skill 附件文件路径或文件名",
                    },
                },
                "required": ["name"],
            },
            handler=make_handler(catalog.load, required=("name",), optional=("filename",)),
        )
    )
    registry.register(
        ToolSpec(
            name="createSkill",
            description=(
                "根据用户要求创建新的 Skill: 在当前项目 .agents/skills/ 下创建英文子目录并生成 SKILL.md。"
                "name 必须是小写字母、数字和连字符组成的名称(如 my-web-search),工具会自动规范大小写与分隔符。"
                "skillContext 必须是完整的 SKILL.md 内容,包含 YAML Frontmatter(name、description)和正文;"
                "若缺少 Frontmatter 或 description,工具会尽量补全。"
                "目标 Skill 已存在时返回提示且不会覆盖。"
                "如需额外的 references/、scripts/ 等目录或辅助文件,请在创建后继续调用 fileOps 工具。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Skill 名称,建议使用小写字母、数字和连字符,如 pdf-tools",
                    },
                    "skillContext": {
                        "type": "string",
                        "description": "要写入 SKILL.md 的完整内容(含 YAML Frontmatter 与正文)",
                    },
                },
                "required": ["name", "skillContext"],
            },
            handler=make_handler(catalog.create, required=("name", "skillContext")),
        )
    )

