# 宠物医院 MCP Server 开发提示词 (Python MVP)

## 项目概述

基于宠物医院 REST API 系统，开发一个符合 MCP 2026-07-28 协议规范的 MCP Server。
**MVP 范围：仅实现 `list_pets` 工具**，支持多参数筛选。

## 技术栈

- **Python**: 3.10+
- **MCP SDK**: `mcp[cli]` v2.1.1 (官方 SDK，支持 2026-07-28)
- **HTTP 客户端**: `httpx` (异步 HTTP 请求)
- **数据源**: 宠物医院 REST API (`http://127.0.0.1:8080`)

## 安装依赖

```bash
pip install "mcp[cli]" httpx
```

## 目录结构

```
pet-hospital-mcp/
├── server.py              # MCP Server 入口
├── tools/
│   └── pets.py            # list_pets 工具实现
├── client/
│   └── pet_api.py         # 宠物医院 API 客户端
├── models/
│   └── types.py           # 数据模型定义
├── config.py              # 配置管理
└── pyproject.toml
```

## 核心代码

### 1. API 客户端 (client/pet_api.py)

```python
import httpx
from typing import Optional

class PetHospitalClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8080"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=10.0)

    async def list_pets(
        self,
        q: Optional[str] = None,
        name: Optional[str] = None,
        owner_name: Optional[str] = None,
        owner_phone: Optional[str] = None,
        species: Optional[str] = None,
        doctor: Optional[str] = None,
        disease: Optional[str] = None,
        status: Optional[str] = None,
        min_cost: Optional[float] = None,
        max_cost: Optional[float] = None,
        sort_by: Optional[str] = None,
        order: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """调用 GET /api/v1/pets"""
        params = {"page": page, "pageSize": page_size}
        
        # 添加可选参数
        if q: params["q"] = q
        if name: params["name"] = name
        if owner_name: params["ownerName"] = owner_name
        if owner_phone: params["ownerPhone"] = owner_phone
        if species: params["species"] = species
        if doctor: params["doctor"] = doctor
        if disease: params["disease"] = disease
        if status: params["status"] = status
        if min_cost is not None: params["min"] = min_cost
        if max_cost is not None: params["max"] = max_cost
        if sort_by: params["sortBy"] = sort_by
        if order: params["order"] = order
        
        response = await self.client.get("/api/v1/pets", params=params)
        response.raise_for_status()
        return response.json()

    async def close(self):
        await self.client.aclose()
```

### 2. 工具定义 (tools/pets.py)

```python
from mcp.server import MCPServer
from mcp.types import Tool, TextContent
from client.pet_api import PetHospitalClient

client = PetHospitalClient()

async def list_pets_handler(
    q: str | None = None,
    name: str | None = None,
    owner_name: str | None = None,
    owner_phone: str | None = None,
    species: str | None = None,
    doctor: str | None = None,
    disease: str | None = None,
    status: str | None = None,
    min_cost: float | None = None,
    max_cost: float | None = None,
    sort_by: str | None = None,
    order: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> list[TextContent]:
    """获取宠物档案列表，支持多维度筛选"""
    try:
        result = await client.list_pets(
            q=q, name=name, owner_name=owner_name, owner_phone=owner_phone,
            species=species, doctor=doctor, disease=disease, status=status,
            min_cost=min_cost, max_cost=max_cost, sort_by=sort_by,
            order=order, page=page, page_size=page_size,
        )
        
        # 格式化输出
        pets = result.get("data", {}).get("items", [])
        total = result.get("data", {}).get("total", 0)
        
        output = f"共 {total} 条记录，当前第 {page} 页\n\n"
        for pet in pets:
            output += format_pet(pet)
            output += "---\n"
        
        return [TextContent(type="text", text=output)]
    except Exception as e:
        return [TextContent(type="text", text=f"错误: {str(e)}")]


def format_pet(pet: dict) -> str:
    """格式化单个宠物信息"""
    return f"""宠物: {pet.get('name', '-')}
ID: {pet.get('id', '-')}
种类: {pet.get('species', '-')} {pet.get('breed', '')}
主人: {pet.get('ownerName', '-')} ({pet.get('ownerPhone', '-')})
医生: {pet.get('doctor', '-')}
疾病: {pet.get('disease', '-')}
状态: {pet.get('status', '-')}
总花费: ¥{pet.get('totalCost', 0)}
就诊次数: {pet.get('visitCount', 0)}

"""


def register_tools(mcp: MCPServer):
    """注册工具到 MCP Server"""
    mcp.add_tool(
        Tool(
            name="list_pets",
            description="获取宠物档案列表，支持按名称、主人、种类、医生、疾病、状态等条件筛选",
            inputSchema={
                "type": "object",
                "properties": {
                    "q": {"type": "string", "description": "全文搜索关键词（跨字段匹配）"},
                    "name": {"type": "string", "description": "宠物姓名"},
                    "owner_name": {"type": "string", "description": "主人姓名"},
                    "owner_phone": {"type": "string", "description": "主人电话"},
                    "species": {"type": "string", "description": "种类：犬/猫/兔/仓鼠/鹦鹉/乌龟/马"},
                    "doctor": {"type": "string", "description": "主治医生"},
                    "disease": {"type": "string", "description": "疾病名称"},
                    "status": {"type": "string", "description": "状态：待就诊/就诊中/住院中/已康复/慢性病随访"},
                    "min_cost": {"type": "number", "description": "最低总花费"},
                    "max_cost": {"type": "number", "description": "最高总花费"},
                    "sort_by": {"type": "string", "enum": ["name", "totalCost", "visitCount"], "description": "排序字段"},
                    "order": {"type": "string", "enum": ["asc", "desc"], "description": "排序方向"},
                    "page": {"type": "integer", "default": 1, "description": "页码"},
                    "page_size": {"type": "integer", "default": 20, "description": "每页条数"},
                },
            },
        ),
        list_pets_handler,
    )
```

### 3. MCP Server 入口 (server.py)

```python
import asyncio
from mcp.server import MCPServer
from mcp.server.stdio import stdio_server
from tools.pets import register_tools

def create_server() -> MCPServer:
    """创建并配置 MCP Server"""
    mcp = MCPServer(
        name="pet-hospital-mcp",
        version="1.0.0",
    )
    
    # 注册工具
    register_tools(mcp)
    
    return mcp

async def main():
    """启动 STDIO 服务器"""
    mcp = create_server()
    
    async with stdio_server(mcp) as (read_stream, write_stream):
        await mcp.run(read_stream, write_stream)

if __name__ == "__main__":
    asyncio.run(main())
```

### 4. HTTP 传输 (可选，server_http.py)

```python
import uvicorn
from mcp.server import MCPServer
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from tools.pets import register_tools

def create_server() -> MCPServer:
    mcp = MCPServer(name="pet-hospital-mcp", version="1.0.0")
    register_tools(mcp)
    return mcp

mcp = create_server()
sse = SseServerTransport("/messages/")

async def handle_sse(request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await mcp.run(streams[0], streams[1])

app = Starlette(
    routes=[
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
    ],
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)
```

## 运行方式

### 方式一：STDIO 模式（推荐本地使用）

```bash
# 直接运行
python server.py

# 或使用 MCP CLI
mcp run server.py
```

### 方式二：HTTP 模式（远程访问）

```bash
# 启动 HTTP 服务器
python server_http.py

# 访问地址: http://localhost:3000/sse
```

## 测试

### 1. 启动宠物医院服务

```bash
cd ../windows
./pethospital.exe
```

### 2. 启动 MCP Server

```bash
python server.py
```

### 3. 使用 MCP Inspector 测试

```bash
npx @modelcontextprotocol/inspector mcp run server.py
```

### 4. 手动测试

```bash
# 通过 STDIO 发送 JSON-RPC 请求
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python server.py

echo '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_pets","arguments":{"species":"犬"}}}' | python server.py
```

## 项目配置 (pyproject.toml)

```toml
[project]
name = "pet-hospital-mcp"
version = "1.0.0"
description = "MCP Server for Pet Hospital REST API"
requires-python = ">=3.10"
dependencies = [
    "mcp[cli]>=2.1.0",
    "httpx>=0.25.0",
]

[project.scripts]
pet-hospital-mcp = "server:main"
```

## MVP 范围说明

### 已实现
- `list_pets` 工具：支持 14 个筛选参数
- STDIO 传输（本地使用）
- HTTP/SSE 传输（远程访问，可选）

### 后续迭代（不在本次范围）
- `get_pet` - 获取单个宠物详情
- `create_pet` - 新增宠物
- `update_pet` / `patch_pet` - 更新宠物
- `delete_pet` - 删除宠物
- 历史病历管理
- 消费明细管理
- 统计分析

## 注意事项

1. **依赖服务**: MCP Server 需要宠物医院 REST API 运行在 `http://127.0.0.1:8080`
2. **异步设计**: 使用 `httpx.AsyncClient` 处理异步 HTTP 请求
3. **错误处理**: 捕获异常并返回用户友好的错误信息
4. **配置灵活**: 支持通过环境变量或参数配置 API 地址
