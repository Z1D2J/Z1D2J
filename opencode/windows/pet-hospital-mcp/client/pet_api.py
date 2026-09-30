import httpx
from typing import Optional
from config import PET_API_BASE_URL, PET_API_TIMEOUT


class PetHospitalClient:
    def __init__(self, base_url: str = PET_API_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            base_url=self.base_url, timeout=PET_API_TIMEOUT
        )

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
        params: dict = {"page": page, "pageSize": page_size}

        if q:
            params["q"] = q
        if name:
            params["name"] = name
        if owner_name:
            params["ownerName"] = owner_name
        if owner_phone:
            params["ownerPhone"] = owner_phone
        if species:
            params["species"] = species
        if doctor:
            params["doctor"] = doctor
        if disease:
            params["disease"] = disease
        if status:
            params["status"] = status
        if min_cost is not None:
            params["min"] = min_cost
        if max_cost is not None:
            params["max"] = max_cost
        if sort_by:
            params["sortBy"] = sort_by
        if order:
            params["order"] = order

        response = await self.client.get("/api/v1/pets", params=params)
        response.raise_for_status()
        return response.json()

    async def create_pet(self, data: dict) -> dict:
        """调用 POST /api/v1/pets"""
        response = await self.client.post("/api/v1/pets", json=data)
        response.raise_for_status()
        return response.json()

    async def close(self):
        await self.client.aclose()
