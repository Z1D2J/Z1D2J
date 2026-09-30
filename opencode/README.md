# opencode

一个围绕 AI 与 MCP（Model Context Protocol）构建的项目集合（monorepo）。仓库内包含三个相互独立、可单独运行的项目。

## 项目概览

| 项目 | 目录 | 技术栈 | 说明 |
| --- | --- | --- | --- |
| AnythingLLM MCP Server | [`opencodeproject/`](opencodeproject/) | Python · MCP | 通过 MCP 协议访问本地 AnythingLLM 实例，共 31 个工具 |
| AnythingLLM 文档上传网页 | [`opencodeproject2/`](opencodeproject2/) | HTML / JavaScript | 单页网页，上传文档到 AnythingLLM 并嵌入工作空间 |
| 宠物医院管理系统 | [`windows/`](windows/) | Go · Python · MCP | REST API + 网页操作界面 + MCP Server，单文件嵌入式数据库 |

## 目录结构

```text
opencode/
├── opencodeproject/            # AnythingLLM MCP Server（Python）
│   ├── src/anythingllm_mcp/    # 源代码
│   ├── tests/                  # 单元测试
│   ├── docs/                   # 文档
│   ├── pyproject.toml          # 项目配置
│   └── README.md               # 详细说明
├── opencodeproject2/           # AnythingLLM 文档上传网页
│   └── index.html              # 单页应用
└── windows/                    # 宠物医院管理系统
    ├── pethospital.exe         # 主程序（Go 编译，已内嵌网页界面）
    ├── data/pet.db             # 单文件数据库（含模拟数据）
    ├── pet-hospital-mcp/       # 宠物医院 MCP Server（Python）
    ├── opencode.json           # opencode 的 MCP 配置
    ├── README.md               # 完整接口与开发文档
    └── README-Windows.md       # Windows 运行说明
```

---

## 1. AnythingLLM MCP Server（`opencodeproject/`）

一个基于 Python 的 MCP Server，用于通过 Model Context Protocol 访问本地安装的 [AnythingLLM](https://anythingllm.com/) 实例。

### 主要功能

- **文档管理**：上传（本地文件 / URL / 纯文本）、列出、删除文档，管理文件夹
- **工作区管理**：创建、配置工作区，添加文档，向量检索与对话
- **线程管理**：创建和管理对话线程
- **系统管理**：查看 / 更新系统设置、向量计数、导出聊天记录
- **用户管理**：用户 CRUD（需多用户模式）

共 31 个 MCP 工具，遵循 MCP 规范，全异步实现，类型安全。

### 快速开始

```bash
cd opencodeproject

# 安装依赖（推荐 uv）
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 ANYTHINGLLM_API_KEY

# 运行服务器
uv run python -m anythingllm_mcp.server
```

在 MCP 客户端（如 Claude Desktop）中配置：

```json
{
  "mcpServers": {
    "anythingllm": {
      "command": "python",
      "args": ["-m", "anythingllm_mcp.server"],
      "env": {
        "ANYTHINGLLM_BASE_URL": "http://localhost:3001",
        "ANYTHINGLLM_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

详细工具列表与用法见 [`opencodeproject/README.md`](opencodeproject/README.md)。

---

## 2. AnythingLLM 文档上传网页（`opencodeproject2/`）

一个单文件网页（[`index.html`](opencodeproject2/index.html)），用浏览器直接打开即可：

- 选择本地文件
- 自动获取第一个工作空间
- 上传文件并嵌入到该工作空间

无需任何后端或依赖，直接双击 HTML 文件即可使用。

---

## 3. 宠物医院管理系统（`windows/`）

一个用 Go 标准库编写的本地宠物医院管理系统，包含三部分：

1. **REST API + 网页界面**（`pethospital.exe`）：启动后浏览器打开 `http://127.0.0.1:8080/` 即可增删改查宠物档案，提供 29 个 REST 接口（查询 / 新增 / 删除 / 批量 / 导出 / 统计）。
2. **单文件嵌入式数据库**（`data/pet.db`）：append-only 日志 + CRC32 校验 + 内存索引，崩溃安全、损坏自愈。
3. **MCP Server**（`pet-hospital-mcp/`）：把宠物医院 REST API 封装成 MCP 工具（MVP 实现 `list_pets`，支持 14 个筛选参数）。

### 快速开始

```bash
cd windows
pethospital.exe          # 双击或命令行启动
```

浏览器打开 <http://127.0.0.1:8080/> 即可使用，无需安装 Go、数据库或任何运行时依赖。

启动宠物医院 MCP Server：

```bash
cd windows/pet-hospital-mcp
python server.py         # STDIO 模式（默认）
# 或
python server_http.py    # HTTP/SSE 模式，http://localhost:3000/sse
```

完整接口文档、数据模型与构建方式见 [`windows/README.md`](windows/README.md)，Windows 使用说明见 [`windows/README-Windows.md`](windows/README-Windows.md)。

---

## License

各子项目均采用 [MIT License](windows/LICENSE)。

- AnythingLLM MCP Server：MIT
- 宠物医院管理系统：MIT（Copyright © 2026 atfa）
