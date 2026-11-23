import os
import jwt
from typing import List
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from services.common.errors import AppException
from services.common.schemas import CurrentUser

security = HTTPBearer(auto_error=False)

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev_super_secret_jwt_key_medical_booking_system_2026")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security)
) -> CurrentUser:
    if not credentials:
        raise AppException(
            status_code=401,
            detail="Yêu cầu cung cấp token xác thực",
            code="UNAUTHORIZED"
        )
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("sub") or payload.get("user_id") or payload.get("id")
        role: str = payload.get("role")
        email: str = payload.get("email")

        if not user_id or not role:
            raise AppException(
                status_code=401,
                detail="Token không chứa đủ thông tin định danh",
                code="INVALID_TOKEN"
            )
        return CurrentUser(id=str(user_id), role=role, email=email)
    except jwt.ExpiredSignatureError:
        raise AppException(
            status_code=401,
            detail="Token đã hết hạn, vui lòng đăng nhập lại",
            code="TOKEN_EXPIRED"
        )
    except jwt.PyJWTError:
        raise AppException(
            status_code=401,
            detail="Token không hợp lệ",
            code="INVALID_TOKEN"
        )


def require_role(allowed_roles: List[str]):
    async def role_checker(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise AppException(
                status_code=403,
                detail="Bạn không có quyền thực hiện thao tác này",
                code="FORBIDDEN"
            )
        return current_user
    return role_checker
