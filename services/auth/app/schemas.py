from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator
from services.auth.app.models import RoleEnum


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, description="Mật khẩu tối thiểu 6 ký tự")
    full_name: str = Field(min_length=2, description="Họ và tên")
    role: str = Field(default="PATIENT", description="PATIENT hoặc DOCTOR")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        role_upper = v.upper()
        if role_upper == "ADMIN":
            raise ValueError("Người dùng không được tự đặt quyền ADMIN khi đăng ký")
        if role_upper not in [RoleEnum.PATIENT.value, RoleEnum.DOCTOR.value]:
            raise ValueError("Vai trò chỉ được là PATIENT hoặc DOCTOR")
        return role_upper


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class UserInToken(BaseModel):
    id: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    user: UserInToken
