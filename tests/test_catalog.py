from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from services.catalog.app.main import app
from services.catalog.app.database import Base, get_db
from services.auth.app.security import create_access_token
import services.catalog.app.redis_client as catalog_redis

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
# TEST CATALOG: DEPARTMENTS
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_departments_crud_and_pagination():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token, _ = create_access_token(user_id="admin-1", role="ADMIN", email="admin@hospital.com")
        patient_token, _ = create_access_token(user_id="patient-1", role="PATIENT", email="patient@hospital.com")

        # 1. Bệnh nhân không được tạo khoa -> 403
        forbidden_res = await client.post(
            "/api/catalog/departments",
            json={"name": "Khoa Mắt", "description": "Khoa mắt"},
            headers={"Authorization": f"Bearer {patient_token}"}
        )
        assert forbidden_res.status_code == 403
        assert forbidden_res.json()["code"] == "FORBIDDEN"

        # 2. Admin tạo khoa -> 201
        res = await client.post(
            "/api/catalog/departments",
            json={"name": "Khoa Mắt", "description": "Chuyên trị bệnh về mắt"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "Khoa Mắt"
        assert "id" in data

        # 3. Tạo trùng tên khoa -> 409
        dup_res = await client.post(
            "/api/catalog/departments",
            json={"name": "Khoa Mắt"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert dup_res.status_code == 409
        assert dup_res.json()["code"] == "DEPARTMENT_EXISTS"

        # 4. Lấy danh sách khoa có phân trang
        list_res = await client.get("/api/catalog/departments?page=1&limit=10")
        assert list_res.status_code == 200
        list_data = list_res.json()
        assert list_data["total"] == 1
        assert list_data["page"] == 1
        assert list_data["limit"] == 10
        assert len(list_data["items"]) == 1
        assert list_data["items"][0]["name"] == "Khoa Mắt"


# -------------------------------------------------------------
# TEST CATALOG: DOCTORS
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_doctors_flow_and_search():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token, _ = create_access_token(user_id="admin-1", role="ADMIN", email="admin@hospital.com")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Tạo khoa trước
        dept_res = await client.post(
            "/api/catalog/departments",
            json={"name": "Khoa Nội"},
            headers=admin_headers
        )
        dept_id = dept_res.json()["id"]

        # Thử tạo bác sĩ với khoa không tồn tại -> 404
        invalid_dept_res = await client.post(
            "/api/catalog/doctors",
            json={
                "department_id": "nonexistent-dept-id",
                "full_name": "BS Trần",
                "price": 200000
            },
            headers=admin_headers
        )
        assert invalid_dept_res.status_code == 404
        assert invalid_dept_res.json()["code"] == "DEPARTMENT_NOT_FOUND"

        # Tạo 2 bác sĩ
        doc1_res = await client.post(
            "/api/catalog/doctors",
            json={
                "department_id": dept_id,
                "full_name": "BS. Trần Minh Nam",
                "title": "Tiến sĩ",
                "price": 300000
            },
            headers=admin_headers
        )
        assert doc1_res.status_code == 201
        doc1_data = doc1_res.json()
        assert doc1_data["full_name"] == "BS. Trần Minh Nam"
        assert doc1_data["department"]["name"] == "Khoa Nội"
        assert doc1_data["price"] == 300000

        doc2_res = await client.post(
            "/api/catalog/doctors",
            json={
                "department_id": dept_id,
                "full_name": "BS. Lê Thị Hồng",
                "title": "Thạc sĩ",
                "price": 250000
            },
            headers=admin_headers
        )
        assert doc2_res.status_code == 201

        # Lấy danh sách lọc theo khoa
        list_all = await client.get(f"/api/catalog/doctors?department_id={dept_id}")
        assert list_all.status_code == 200
        assert list_all.json()["total"] == 2

        # Tìm kiếm theo tên (query param q)
        search_res = await client.get("/api/catalog/doctors?q=Minh")
        assert search_res.status_code == 200
        search_data = search_res.json()
        assert search_data["total"] == 1
        assert search_data["items"][0]["full_name"] == "BS. Trần Minh Nam"


# -------------------------------------------------------------
# TEST CATALOG: TIME SLOTS & OVERLAP CHECK
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_time_slots_and_overlap_rejection():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token, _ = create_access_token(user_id="admin-1", role="ADMIN", email="admin@hospital.com")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Tạo khoa và bác sĩ
        dept_res = await client.post("/api/catalog/departments", json={"name": "Khoa Nhi"}, headers=admin_headers)
        dept_id = dept_res.json()["id"]

        doc_res = await client.post(
            "/api/catalog/doctors",
            json={"department_id": dept_id, "full_name": "BS Nhi Đồng", "price": 200000},
            headers=admin_headers
        )
        doc_id = doc_res.json()["id"]

        # 1. Thêm khung giờ sai khoảng thời gian (start >= end) -> 400
        start = datetime.now(timezone.utc) + timedelta(days=2, hours=9)
        end = start - timedelta(minutes=30)
        invalid_time_res = await client.post(
            f"/api/catalog/doctors/{doc_id}/slots",
            json={"start_time": start.isoformat(), "end_time": end.isoformat()},
            headers=admin_headers
        )
        assert invalid_time_res.status_code == 400
        assert invalid_time_res.json()["code"] == "INVALID_TIME_RANGE"

        # 2. Thêm khung giờ hợp lệ 9:00 - 9:30 -> 201
        start1 = datetime.now(timezone.utc) + timedelta(days=2, hours=9)
        end1 = start1 + timedelta(minutes=30)
        slot1_res = await client.post(
            f"/api/catalog/doctors/{doc_id}/slots",
            json={"start_time": start1.isoformat(), "end_time": end1.isoformat()},
            headers=admin_headers
        )
        assert slot1_res.status_code == 201
        slot1_data = slot1_res.json()
        assert slot1_data["is_available"] is True

        # 3. Thêm khung giờ chồng lấn (ví dụ 9:15 - 9:45) -> 409 SLOT_OVERLAP (SRS FR-2.5)
        start_overlap = start1 + timedelta(minutes=15)
        end_overlap = start_overlap + timedelta(minutes=30)
        overlap_res = await client.post(
            f"/api/catalog/doctors/{doc_id}/slots",
            json={"start_time": start_overlap.isoformat(), "end_time": end_overlap.isoformat()},
            headers=admin_headers
        )
        assert overlap_res.status_code == 409
        assert overlap_res.json()["code"] == "SLOT_OVERLAP"

        # 4. Lấy danh sách khung giờ của bác sĩ
        slots_list = await client.get(f"/api/catalog/doctors/{doc_id}/slots")
        assert slots_list.status_code == 200
        assert slots_list.json()["total"] == 1


# -------------------------------------------------------------
# TEST CATALOG: REDIS CACHING & FALLBACK
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_redis_cache_and_graceful_fallback():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Giả lập mock bộ nhớ đệm in-memory giả lập Redis
        in_memory_cache = {}

        async def mock_get_cache(key: str):
            return in_memory_cache.get(key)

        async def mock_set_cache(key: str, value: dict | list, ttl_seconds: int = 300):
            in_memory_cache[key] = value

        async def mock_invalidate_cache(pattern: str = "catalog:*"):
            in_memory_cache.clear()

        with patch("services.catalog.app.routers.catalog.get_cache", side_effect=mock_get_cache), \
             patch("services.catalog.app.routers.catalog.set_cache", side_effect=mock_set_cache), \
             patch("services.catalog.app.routers.catalog.invalidate_catalog_cache", side_effect=mock_invalidate_cache):

            # Lần 1: Chưa có cache -> ghi vào cache
            res1 = await client.get("/api/catalog/departments")
            assert res1.status_code == 200
            assert len(in_memory_cache) > 0

            # Lần 2: Đọc trực tiếp từ mock cache
            res2 = await client.get("/api/catalog/departments")
            assert res2.status_code == 200

            # Khi tạo mới -> cache bị xóa (invalidation)
            admin_token, _ = create_access_token(user_id="admin-1", role="ADMIN", email="admin@hospital.com")
            await client.post(
                "/api/catalog/departments",
                json={"name": "Khoa Mới"},
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert len(in_memory_cache) == 0

        # Kiểm tra Fallback khi Redis mất kết nối (get_cache trả về None)
        # Hệ thống vẫn phải hoạt động bình thường bằng cách truy vấn trực tiếp DB
        with patch("services.catalog.app.routers.catalog.get_cache", return_value=None):
            res_fallback = await client.get("/api/catalog/departments")
            assert res_fallback.status_code == 200
