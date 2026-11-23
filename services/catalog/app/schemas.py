from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class DepartmentOut(BaseModel):
    id: str
    name: str
    description: str | None = None

    model_config = ConfigDict(from_attributes=True)


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = None


class DepartmentSimple(BaseModel):
    id: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class DoctorOut(BaseModel):
    id: str
    full_name: str
    title: str
    department: DepartmentSimple
    price: int

    model_config = ConfigDict(from_attributes=True)


class DoctorCreate(BaseModel):
    department_id: str
    full_name: str = Field(min_length=2, max_length=255)
    title: str = "Bác sĩ Chuyên khoa"
    price: int = Field(default=250000, ge=0)
    user_id: str | None = None


class SlotOut(BaseModel):
    id: str
    doctor_id: str
    start_time: datetime
    end_time: datetime
    is_available: bool

    model_config = ConfigDict(from_attributes=True)


class SlotCreate(BaseModel):
    start_time: datetime
    end_time: datetime
