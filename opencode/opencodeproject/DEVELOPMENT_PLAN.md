# AnythingLLM MCP Server 开发计划

## 1. 项目概述

开发一个MCP Server，用于访问本地安装的AnythingLLM实例，通过MCP协议暴露AnythingLLM的功能给AI助手。

### 1.1 技术栈
- **语言**: Python 3.10+
- **MCP SDK**: `mcp[cli]` v2 (支持2026-07-28规范)
- **HTTP客户端**: `httpx2` (异步HTTP请求)
- **配置管理**: 环境变量 + `.env`文件

### 1.2 AnythingLLM实例信息
- **地址**: http://localhost:3001
- **API密钥**: your-api-key-here
- **API文档**: http://localhost:3001/api/docs/

## 2. MCP工具设计

基于AnythingLLM API分析，设计以下MCP工具分类：

### 2.1 认证工具 (Authentication)
| 工具名称 | 功能 | 参数 |
|----------|------|------|
| `verify_api_key` | 验证API密钥是否有效 | 无 |

### 2.2 文档管理工具 (Documents)
| 工具名称 | 功能 | 参数 |
|----------|------|------|
| `upload_document` | 上传文件到AnythingLLM | `file_path`, `folder_name`(可选), `add_to_workspaces`(可选) |
| `upload_document_from_url` | 通过URL上传文档 | `url`, `add_to_workspaces`(可选), `metadata`(可选) |
| `upload_raw_text` | 上传原始文本 | `text_content`, `add_to_workspaces`(可选), `metadata`(可选) |
| `list_documents` | 列出所有文档 | `folder_name`(可选) |
| `get_document` | 获取单个文档详情 | `document_name` |
| `delete_document` | 永久删除文档 | `document_names` (数组) |
| `create_folder` | 创建文档文件夹 | `folder_name` |
| `delete_folder` | 删除文档文件夹 | `folder_name` |
| `move_files` | 移动文件 | `files` (数组，包含from和to) |

### 2.3 工作区管理工具 (Workspaces)
| 工具名称 | 功能 | 参数 |
|----------|------|------|
| `create_workspace` | 创建新工作区 | `name`, `settings`(可选) |
| `list_workspaces` | 列出所有工作区 | 无 |
| `get_workspace` | 获取工作区详情 | `workspace_slug` |
| `delete_workspace` | 删除工作区 | `workspace_slug` |
| `update_workspace` | 更新工作区设置 | `workspace_slug`, `settings` |
| `add_documents_to_workspace` | 添加文档到工作区 | `workspace_slug`, `document_paths` |
| `remove_documents_from_workspace` | 从工作区移除文档 | `workspace_slug`, `document_paths` |
| `chat_with_workspace` | 与工作区聊天 | `workspace_slug`, `message`, `mode`(可选) |
| `vector_search` | 向量搜索 | `workspace_slug`, `query`, `top_n`(可选) |

### 2.4 线程管理工具 (Workspace Threads)
| 工具名称 | 功能 | 参数 |
|----------|------|------|
| `create_thread` | 创建新线程 | `workspace_slug`, `name` |
| `list_threads` | 列出工作区线程 | `workspace_slug` |
| `delete_thread` | 删除线程 | `workspace_slug`, `thread_slug` |
| `chat_with_thread` | 与线程聊天 | `workspace_slug`, `thread_slug`, `message` |

### 2.5 系统管理工具 (System)
| 工具名称 | 功能 | 参数 |
|----------|------|------|
| `get_system_settings` | 获取系统设置 | 无 |
| `update_system_settings` | 更新系统设置 | `settings` |
| `get_vector_count` | 获取向量总数 | 无 |
| `export_chats` | 导出聊天记录 | `export_type`(可选: json, jsonl, csv) |

### 2.6 用户管理工具 (Admin - 需要多用户模式)
| 工具名称 | 功能 | 参数 |
|----------|------|------|
| `list_users` | 列出所有用户 | 无 |
| `create_user` | 创建新用户 | `username`, `password`, `role`(可选) |
| `update_user` | 更新用户信息 | `user_id`, `updates` |
| `delete_user` | 删除用户 | `user_id` |

## 3. 项目结构

```
anythingllm-mcp-server/
├── src/
│   └── anythingllm_mcp/
│       ├── __init__.py
│       ├── server.py          # MCP Server主入口
│       ├── client.py          # AnythingLLM API客户端
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── auth.py        # 认证工具
│       │   ├── documents.py   # 文档管理工具
│       │   ├── workspaces.py  # 工作区管理工具
│       │   ├── threads.py     # 线程管理工具
│       │   ├── system.py      # 系统管理工具
│       │   └── admin.py       # 用户管理工具
│       ├── models.py          # 数据模型定义
│       └── config.py          # 配置管理
├── tests/
│   ├── __init__.py
│   ├── test_client.py
│   ├── test_tools.py
│   └── conftest.py
├── docs/
│   ├── README.md
│   └── API.md
├── pyproject.toml
├── requirements.txt
├── .env.example
└── DEVELOPMENT_PLAN.md
```

## 4. 实现步骤

### 阶段1: 基础框架 (1-2天)
1. 创建项目结构
2. 配置依赖管理 (pyproject.toml)
3. 实现配置管理 (config.py)
4. 实现AnythingLLM API客户端 (client.py)
5. 创建MCP Server基础框架 (server.py)

### 阶段2: 核心工具实现 (2-3天)
1. 实现认证工具
2. 实现文档管理工具
3. 实现工作区管理工具
4. 实现聊天功能

### 阶段3: 高级功能 (1-2天)
1. 实现线程管理工具
2. 实现系统管理工具
3. 实现用户管理工具
4. 添加错误处理和日志

### 阶段4: 测试与文档 (1天)
1. 编写单元测试
2. 编写集成测试
3. 编写使用文档
4. 配置MCP Inspector测试

## 5. 配置管理

### 5.1 环境变量
```bash
# .env.example
ANYTHINGLLM_BASE_URL=http://localhost:3001
ANYTHINGLLM_API_KEY=your-api-key-here
ANYTHINGLLM_TIMEOUT=30
```

### 5.2 MCP Server配置
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

## 6. 错误处理策略

### 6.1 API错误处理
- 认证失败 (403): 返回明确的错误信息
- 资源不存在 (404): 返回资源未找到错误
- 服务器错误 (500): 返回服务器错误信息
- 超时错误: 返回超时提示

### 6.2 MCP工具错误处理
- 参数验证错误: 返回参数错误信息
- API调用错误: 包装为MCP工具错误
- 网络错误: 返回网络连接错误

## 7. 安全考虑

### 7.1 API密钥安全
- 使用环境变量存储API密钥
- 不在日志中记录完整API密钥
- 支持API密钥轮换

### 7.2 输入验证
- 验证所有工具参数
- 防止路径遍历攻击
- 限制文件上传大小

## 8. 测试策略

### 8.1 单元测试
- 测试API客户端的各种方法
- 测试工具参数验证
- 测试错误处理

### 8.2 集成测试
- 测试完整的MCP工具调用流程
- 测试与AnythingLLM API的实际交互

### 8.3 端到端测试
- 使用MCP Inspector进行测试
- 测试与AI助手的集成

## 9. 部署说明

### 9.1 本地部署
```bash
# 安装依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 启动MCP Server
python -m anythingllm_mcp.server
```

### 9.2 与AI助手集成
将MCP Server配置添加到AI助手的配置文件中（如Claude Desktop的`claude_desktop_config.json`）。

## 10. 后续扩展

### 10.1 功能扩展
- 支持流式聊天响应
- 支持文件上传进度
- 支持批量操作
- 支持Webhook通知

### 10.2 性能优化
- 实现API请求缓存
- 实现连接池
- 实现请求重试机制

### 10.3 监控和日志
- 实现结构化日志
- 实现性能监控
- 实现审计日志