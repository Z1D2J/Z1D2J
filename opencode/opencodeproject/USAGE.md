# AnythingLLM MCP Server - 使用说明

## 项目概述

这是一个MCP Server，用于访问本地安装的AnythingLLM实例。它通过MCP协议暴露AnythingLLM的功能给AI助手。

## 技术栈

- **语言**: Python 3.10+
- **MCP SDK**: `mcp[cli]` v2 (支持2026-07-28规范)
- **HTTP客户端**: `httpx2` (异步HTTP请求)
- **配置管理**: 环境变量 + `.env`文件

## 项目结构

```
anythingllm-mcp-server/
├── src/
│   └── anythingllm_mcp/
│       ├── __init__.py
│       ├── __main__.py
│       ├── server.py          # MCP Server主入口
│       ├── client.py          # AnythingLLM API客户端
│       ├── config.py          # 配置管理
│       ├── models.py          # 数据模型定义
│       └── tools/
│           ├── __init__.py
│           ├── auth.py        # 认证工具
│           ├── documents.py   # 文档管理工具
│           ├── workspaces.py  # 工作区管理工具
│           ├── threads.py     # 线程管理工具
│           ├── system.py      # 系统管理工具
│           └── admin.py       # 用户管理工具
├── tests/
│   ├── conftest.py
│   ├── test_client.py
│   └── test_tools.py
├── docs/
│   └── README.md
├── pyproject.toml
├── .env.example
├── README.md
└── example.py
```

## 快速开始

### 1. 安装依赖

```bash
# 使用uv (推荐)
uv add "mcp[cli]" httpx2 python-dotenv pydantic

# 或使用pip
pip install "mcp[cli]" httpx2 python-dotenv pydantic
```

### 2. 配置环境

复制`.env.example`到`.env`并更新配置：

```bash
cp .env.example .env
```

编辑`.env`文件：
```bash
ANYTHINGLLM_BASE_URL=http://localhost:3001
ANYTHINGLLM_API_KEY=your-api-key-here
```

### 3. 运行服务器

```bash
# 使用uv
uv run python -m anythingllm_mcp.server

# 或直接使用python
python -m anythingllm_mcp.server
```

### 4. 配置MCP客户端

将以下配置添加到你的MCP客户端配置文件中（如Claude Desktop的`claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "anythingllm": {
      "command": "python",
      "args": ["-m", "anythingllm_mcp.server"],
      "cwd": "D:\\ZDJ\\opencodeproject",
      "env": {
        "ANYTHINGLLM_BASE_URL": "http://localhost:3001",
        "ANYTHINGLLM_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

## 可用工具

### 认证工具
- `tool_verify_api_key` - 验证API密钥是否有效

### 文档管理工具
- `tool_upload_document` - 上传文件
- `tool_upload_document_from_url` - 从URL上传文档
- `tool_upload_raw_text` - 上传原始文本
- `tool_list_documents` - 列出所有文档
- `tool_get_document` - 获取文档详情
- `tool_delete_document` - 删除文档
- `tool_create_folder` - 创建文件夹
- `tool_delete_folder` - 删除文件夹
- `tool_move_files` - 移动文件

### 工作区管理工具
- `tool_create_workspace` - 创建工作区
- `tool_list_workspaces` - 列出所有工作区
- `tool_get_workspace` - 获取工作区详情
- `tool_delete_workspace` - 删除工作区
- `tool_update_workspace` - 更新工作区设置
- `tool_add_documents_to_workspace` - 添加文档到工作区
- `tool_remove_documents_from_workspace` - 从工作区移除文档
- `tool_chat_with_workspace` - 与工作区聊天
- `tool_vector_search` - 向量搜索

### 线程管理工具
- `tool_create_thread` - 创建线程
- `tool_list_threads` - 列出工作区线程
- `tool_delete_thread` - 删除线程
- `tool_chat_with_thread` - 与线程聊天

### 系统管理工具
- `tool_get_system_settings` - 获取系统设置
- `tool_update_system_settings` - 更新系统设置
- `tool_get_vector_count` - 获取向量总数
- `tool_export_chats` - 导出聊天记录

### 用户管理工具 (Admin)
- `tool_list_users` - 列出所有用户
- `tool_create_user` - 创建用户
- `tool_update_user` - 更新用户
- `tool_delete_user` - 删除用户

## 开发指南

### 运行测试

```bash
pytest
```

### 代码质量检查

```bash
# 代码检查
ruff check .

# 类型检查
mypy src/

# 代码格式化
ruff format .
```

### 使用MCP Inspector

```bash
uv run mcp dev src/anythingllm_mcp/server.py
```

## 示例代码

查看`example.py`文件了解如何使用MCP客户端与服务器交互。

## 故障排除

### 1. 服务器无法启动

确保：
- 已安装所有依赖
- 环境变量已正确配置
- AnythingLLM实例正在运行

### 2. API密钥验证失败

检查：
- API密钥是否正确
- AnythingLLM实例是否可达
- 网络连接是否正常

### 3. 工具调用失败

检查：
- 参数是否正确
- 工作区/文档是否存在
- 权限是否足够

## 许可证

MIT License