from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from services.auth.app.database import get_db
from services.auth.app.models import User, RoleEnum
from services.auth.app.schemas import RegisterRequest, LoginRequest, UserResponse, TokenResponse, UserInToken
from services.auth.app.security import hash_password, verify_password, create_access_token
from services.common.errors import AppException
from services.common.auth import get_current_user
from services.common.schemas import CurrentUser

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # 1. Kiểm tra email đã tồn tại hay chưa
    stmt = select(User).where(User.email == body.email)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email này đã được sử dụng",
            code="EMAIL_EXISTS"
        )

    # 2. Hash mật khẩu và tạo bản ghi User mới
    hashed = hash_password(body.password)
    new_user = User(
        email=body.email,
        hashed_password=hashed,
        full_name=body.full_name,
        role=RoleEnum(body.role)
    )
    db.add(new_user)
    try:
        await db.commit()
    except IntegrityError:
        # Hai request cùng đăng ký một email: bước kiểm tra phía trên không
        # chặn được, nhưng unique index trong database thì có. Bắt lỗi này để
        # trả 409 thay vì 500.
        await db.rollback()
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email này đã được sử dụng",
            code="EMAIL_EXISTS"
        )
    await db.refresh(new_user)

    return new_user


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    # 1. Tìm user theo email
    stmt = select(User).where(User.email == body.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    # 2. Kiểm tra tài khoản và mật khẩu
    # Trả về cùng thông báo lỗi 401 để tránh lộ thông tin email nào đã tồn tại trong hệ thống (Quy định SRS FR-1.4)
    if not user or not verify_password(body.password, user.hashed_password):
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác",
            code="INVALID_CREDENTIALS"
        )

    # 3. Tạo JWT access token có hạn 1 giờ
    access_token, expires_in = create_access_token(
        user_id=user.id,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        email=user.email
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserInToken(
            id=str(user.id),
            role=user.role.value if hasattr(user.role, "value") else str(user.role)
        )
    )


@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(User).where(User.id == current_user.id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy người dùng",
            code="USER_NOT_FOUND"
        )

    return user
