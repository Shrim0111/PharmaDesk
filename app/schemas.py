
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserCreate(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()

        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("Enter a valid email address")

        return value


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MedicineCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    sku: str = Field(..., min_length=1, max_length=100)
    reorder_threshold: int = Field(default=10, ge=0)

    @field_validator("name", "sku")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Value cannot be empty")

        return value


class MedicineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sku: str
    reorder_threshold: int


class PaginatedMedicineResponse(BaseModel):
    items: list[MedicineResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class BatchCreate(BaseModel):
    medicine_id: int = Field(..., gt=0)
    batch_no: str = Field(..., min_length=1, max_length=100)
    quantity: int = Field(..., gt=0)
    expiry_date: date

    @field_validator("batch_no")
    @classmethod
    def validate_batch_no(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Batch number cannot be empty")

        return value


class BatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    medicine_id: int
    batch_no: str
    quantity: int
    expiry_date: date
    status: str
    created_at: datetime


class DispenseRequest(BaseModel):
    quantity: int = Field(..., gt=0)



