import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
from sqlalchemy import select

from services.auth.app.main import app
from services.auth.app.database import Base, get_db
from services.auth.app.models import User
from services.auth.app.config import settings
from services.common.auth import require_role, get_current_user
from services.common.schemas import CurrentUser
from fastapi import Depends

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# -------------------------------------------------------------
# TEST AUTH: REGISTER
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_register_patient_success():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "email": "patient_test@example.com",
            "password": "Password123!",
            "full_name": "Nguyễn Văn A",
            "role": "PATIENT"
        }
        res = await client.post("/api/auth/register", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["email"] == "patient_test@example.com"
        assert data["full_name"] == "Nguyễn Văn A"
        assert data["role"] == "PATIENT"
        assert "id" in data
        assert "created_at" in data

        # Kiểm tra mật khẩu trong DB thực sự là bcrypt, KHÔNG lưu plain text
        async with TestingSessionLocal() as session:
            stmt = select(User).where(User.email == "patient_test@example.com")
            user_in_db = (await session.execute(stmt)).scalar_one()
            assert user_in_db.hashed_password != "Password123!"
            assert bcrypt.checkpw("Password123!".encode(), user_in_db.hashed_password.encode())


@pytest.mark.asyncio
async def test_register_doctor_success():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "email": "doctor_test@example.com",
            "password": "DoctorPass123",
            "full_name": "BS Trần B",
            "role": "DOCTOR"
        }
        res = await client.post("/api/auth/register", json=payload)
        assert res.status_code == 201
        assert res.json()["role"] == "DOCTOR"


@pytest.mark.asyncio
async def test_register_admin_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "email": "admin_hacker@example.com",
            "password": "Password123!",
            "full_name": "Hacker",
            "role": "ADMIN"
        }
        res = await client.post("/api/auth/register", json=payload)
        assert res.status_code == 422
        assert res.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_register_duplicate_email_conflict():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "email": "duplicate@example.com",
            "password": "Password123!",
            "full_name": "Người dùng 1",
            "role": "PATIENT"
        }
        res1 = await client.post("/api/auth/register", json=payload)
        assert res1.status_code == 201

        # Đăng ký lần 2 cùng email phải trả về 409 EMAIL_EXISTS
        res2 = await client.post("/api/auth/register", json=payload)
        assert res2.status_code == 409
        assert res2.json()["code"] == "EMAIL_EXISTS"


@pytest.mark.asyncio
async def test_register_invalid_inputs():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Email sai định dạng
        res1 = await client.post("/api/auth/register", json={
            "email": "not-an-email",
            "password": "password123",
            "full_name": "Tên",
            "role": "PATIENT"
        })
        assert res1.status_code == 422

        # Password quá ngắn (< 6 ký tự)
        res2 = await client.post("/api/auth/register", json={
            "email": "valid@example.com",
            "password": "123",
            "full_name": "Tên",
            "role": "PATIENT"
        })
        assert res2.status_code == 422


# -------------------------------------------------------------
# TEST AUTH: LOGIN & JWT
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_login_success_and_jwt_format():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/auth/register", json={
            "email": "login_user@example.com",
            "password": "CorrectPassword123",
            "full_name": "Khách hàng",
            "role": "PATIENT"
        })

        res = await client.post("/api/auth/login", json={
            "email": "login_user@example.com",
            "password": "CorrectPassword123"
        })
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 3600
        assert data["user"]["role"] == "PATIENT"

        # Giải mã và kiểm tra cấu trúc JWT
        token = data["access_token"]
        decoded = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        assert decoded["email"] == "login_user@example.com"
        assert decoded["role"] == "PATIENT"
        assert "exp" in decoded


@pytest.mark.asyncio
async def test_login_failed_same_error_message():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/auth/register", json={
            "email": "exist@example.com",
            "password": "CorrectPassword123",
            "full_name": "Khách hàng",
            "role": "PATIENT"
        })

        # Sai mật khẩu
        res_wrong_pw = await client.post("/api/auth/login", json={
            "email": "exist@example.com",
            "password": "WrongPassword!"
        })
        assert res_wrong_pw.status_code == 401
        assert res_wrong_pw.json()["code"] == "INVALID_CREDENTIALS"

        # Sai email (không tồn tại)
        res_wrong_email = await client.post("/api/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "AnyPassword"
        })
        assert res_wrong_email.status_code == 401
        assert res_wrong_email.json()["code"] == "INVALID_CREDENTIALS"

        # Đảm bảo thông báo lỗi HOÀN TOÀN GIỐNG NHAU để chống lộ thông tin tài khoản
        assert res_wrong_pw.json()["detail"] == res_wrong_email.json()["detail"]


# -------------------------------------------------------------
# TEST AUTH: GET /ME & TOKEN VALIDATION
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_token_missing_and_invalid():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Không truyền token
        res_missing = await client.get("/api/auth/me")
        assert res_missing.status_code == 401
        assert res_missing.json()["code"] == "UNAUTHORIZED"

        # Token sai định dạng / rác
        res_bad = await client.get("/api/auth/me", headers={"Authorization": "Bearer junk-token-12345"})
        assert res_bad.status_code == 401
        assert res_bad.json()["code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_token_expired():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Tạo token đã hết hạn 10 phút trước
        expired_payload = {
            "sub": "user-uuid-123",
            "id": "user-uuid-123",
            "email": "expired@example.com",
            "role": "PATIENT",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=10)
        }
        expired_token = jwt.encode(expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert res.status_code == 401
        assert res.json()["code"] == "TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_get_me_success():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        reg_res = await client.post("/api/auth/register", json={
            "email": "me_test@example.com",
            "password": "MyPassword123",
            "full_name": "Lê Văn C",
            "role": "PATIENT"
        })
        user_id = reg_res.json()["id"]

        login_res = await client.post("/api/auth/login", json={
            "email": "me_test@example.com",
            "password": "MyPassword123"
        })
        token = login_res.json()["access_token"]

        me_res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_res.status_code == 200
        data = me_res.json()
        assert data["id"] == user_id
        assert data["email"] == "me_test@example.com"
        assert data["full_name"] == "Lê Văn C"
        assert data["role"] == "PATIENT"
