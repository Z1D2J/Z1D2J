from mcp.server import MCPServer
from mcp.types import TextContent
from client.pet_api import PetHospitalClient

client = PetHospitalClient()


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
            q=q,
            name=name,
            owner_name=owner_name,
            owner_phone=owner_phone,
            species=species,
            doctor=doctor,
            disease=disease,
            status=status,
            min_cost=min_cost,
            max_cost=max_cost,
            sort_by=sort_by,
            order=order,
            page=page,
            page_size=page_size,
        )

        pets = result.get("data", {}).get("items", [])
        total = result.get("data", {}).get("total", 0)

        output = f"共 {total} 条记录，当前第 {page} 页\n\n"
        for pet in pets:
            output += format_pet(pet)
            output += "---\n"

        return [TextContent(type="text", text=output)]
    except Exception as e:
        return [TextContent(type="text", text=f"错误: {str(e)}")]


async def create_pet_handler(
    name: str,
    species: str,
    doctor: str,
    breed: str = "",
    gender: str = "",
    age_months: int = 0,
    color: str = "",
    chip_no: str = "",
    owner_name: str = "",
    owner_phone: str = "",
    owner_addr: str = "",
    disease: str = "",
    status: str = "待就诊",
    allergy: str = "",
) -> list[TextContent]:
    """新增宠物档案"""
    try:
        data = {"name": name, "species": species, "doctor": doctor}
        if breed:
            data["breed"] = breed
        if gender:
            data["gender"] = gender
        if age_months:
            data["ageMonths"] = age_months
        if color:
            data["color"] = color
        if chip_no:
            data["chipNo"] = chip_no
        if owner_name:
            data["ownerName"] = owner_name
        if owner_phone:
            data["ownerPhone"] = owner_phone
        if owner_addr:
            data["ownerAddr"] = owner_addr
        if disease:
            data["disease"] = disease
        if status:
            data["status"] = status
        if allergy:
            data["allergy"] = allergy

        result = await client.create_pet(data)
        pet = result.get("data", {})

        output = f"新增成功！\n\n{format_pet(pet)}"
        return [TextContent(type="text", text=output)]
    except Exception as e:
        return [TextContent(type="text", text=f"错误: {str(e)}")]


def register_tools(mcp: MCPServer):
    """注册工具到 MCP Server"""
    mcp.add_tool(
        list_pets_handler,
        name="list_pets",
        description="获取宠物档案列表，支持按名称、主人、种类、医生、疾病、状态等条件筛选",
    )
    mcp.add_tool(
        create_pet_handler,
        name="create_pet",
        description="新增宠物档案，必须提供宠物姓名和种类，可选主人、医生、疾病等信息",
    )
