from pydantic import BaseModel
from typing import Optional


class Pet(BaseModel):
    id: str
    name: str
    species: str = ""
    breed: str = ""
    gender: str = ""
    ageMonths: int = 0
    color: str = ""
    chipId: str = ""
    ownerName: str = ""
    ownerPhone: str = ""
    address: str = ""
    doctor: str = ""
    disease: str = ""
    status: str = ""
    allergy: str = ""
    notes: str = ""
    totalCost: float = 0
    visitCount: int = 0


class PetListResponse(BaseModel):
    code: int
    message: str
    data: dict
    time: str = ""
