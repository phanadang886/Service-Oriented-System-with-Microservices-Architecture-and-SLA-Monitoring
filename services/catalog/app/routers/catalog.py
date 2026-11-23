from datetime import date, datetime, time, timezone
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from services.catalog.app.database import get_db
from services.catalog.app.models import Department, Doctor, TimeSlot
from services.catalog.app.schemas import (
    DepartmentOut, DepartmentCreate,
    DoctorOut, DoctorCreate,
    SlotOut, SlotCreate
)
from services.catalog.app.redis_client import get_cache, set_cache, invalidate_catalog_cache
from services.common.errors import AppException
from services.common.schemas import PaginationResponse, CurrentUser
from services.common.auth import require_role

router = APIRouter(prefix="/api/catalog", tags=["Catalog"])


# -------------------------------------------------------------
# 1. DEPARTMENTS
# -------------------------------------------------------------
@router.get("/departments", response_model=PaginationResponse[DepartmentOut])
async def list_departments(
    page: int = Query(1, ge=1, description="Số trang"),
    limit: int = Query(20, ge=1, le=100, description="Số lượng mỗi trang"),
    db: AsyncSession = Depends(get_db)
):
    cache_key = f"catalog:departments:{page}:{limit}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    count_stmt = select(func.count(Department.id))
    total = (await db.execute(count_stmt)).scalar() or 0

    offset = (page - 1) * limit
    stmt = select(Department).order_by(Department.name).offset(offset).limit(limit)
    items = (await db.execute(stmt)).scalars().all()

    result = {
        "items": [DepartmentOut.model_validate(item).model_dump() for item in items],
        "total": total,
        "page": page,
        "limit": limit
    }

    await set_cache(cache_key, result)
    return result


@router.post("/departments", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
async def create_department(
    body: DepartmentCreate,
    current_user: CurrentUser = Depends(require_role(["ADMIN"])),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Department).where(Department.name == body.name)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Khoa '{body.name}' đã tồn tại",
            code="DEPARTMENT_EXISTS"
        )

    dept = Department(name=body.name, description=body.description)
    db.add(dept)
    await db.commit()
    await db.refresh(dept)

    await invalidate_catalog_cache("catalog:departments:*")
    return dept


# -------------------------------------------------------------
# 2. DOCTORS
# -------------------------------------------------------------
@router.get("/doctors", response_model=PaginationResponse[DoctorOut])
async def list_doctors(
    department_id: str | None = Query(None, description="Lọc theo mã khoa"),
    q: str | None = Query(None, description="Tìm kiếm theo tên bác sĩ"),
    page: int = Query(1, ge=1, description="Số trang"),
    limit: int = Query(20, ge=1, le=100, description="Số lượng mỗi trang"),
    db: AsyncSession = Depends(get_db)
):
    cache_key = f"catalog:doctors:{department_id or 'all'}:{q or 'all'}:{page}:{limit}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    filters = [Doctor.is_active == True]
    if department_id:
        filters.append(Doctor.department_id == department_id)
    if q:
        filters.append(Doctor.full_name.ilike(f"%{q.strip()}%"))

    count_stmt = select(func.count(Doctor.id)).where(*filters)
    total = (await db.execute(count_stmt)).scalar() or 0

    offset = (page - 1) * limit
    stmt = (
        select(Doctor)
        .options(selectinload(Doctor.department))
        .where(*filters)
        .order_by(Doctor.full_name)
        .offset(offset)
        .limit(limit)
    )
    items = (await db.execute(stmt)).scalars().all()

    doctor_list = []
    for item in items:
        doctor_list.append({
            "id": item.id,
            "full_name": item.full_name,
            "title": item.title,
            "department": {
                "id": item.department.id,
                "name": item.department.name
            } if item.department else {"id": "", "name": ""},
            "price": item.price
        })

    result = {
        "items": doctor_list,
        "total": total,
        "page": page,
        "limit": limit
    }

    await set_cache(cache_key, result)
    return result


@router.post("/doctors", response_model=DoctorOut, status_code=status.HTTP_201_CREATED)
async def create_doctor(
    body: DoctorCreate,
    current_user: CurrentUser = Depends(require_role(["ADMIN"])),
    db: AsyncSession = Depends(get_db)
):
    dept_stmt = select(Department).where(Department.id == body.department_id)
    dept = (await db.execute(dept_stmt)).scalar_one_or_none()
    if not dept:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Khoa khám không tồn tại",
            code="DEPARTMENT_NOT_FOUND"
        )

    doctor = Doctor(
        department_id=body.department_id,
        full_name=body.full_name,
        title=body.title,
        price=body.price,
        user_id=body.user_id,
        is_active=True
    )
    db.add(doctor)
    await db.commit()
    await db.refresh(doctor)

    await invalidate_catalog_cache("catalog:doctors:*")

    return {
        "id": doctor.id,
        "full_name": doctor.full_name,
        "title": doctor.title,
        "department": {
            "id": dept.id,
            "name": dept.name
        },
        "price": doctor.price
    }


# -------------------------------------------------------------
# 3. TIME SLOTS
# -------------------------------------------------------------
@router.get("/doctors/{doctor_id}/slots", response_model=PaginationResponse[SlotOut])
async def list_doctor_slots(
    doctor_id: str,
    slot_date: date | None = Query(None, alias="date", description="Lọc theo ngày khám (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="Số trang"),
    limit: int = Query(50, ge=1, le=100, description="Số lượng mỗi trang"),
    db: AsyncSession = Depends(get_db)
):
    # Kiểm tra bác sĩ có tồn tại không
    doc_stmt = select(Doctor).where(Doctor.id == doctor_id)
    doc = (await db.execute(doc_stmt)).scalar_one_or_none()
    if not doc:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bác sĩ không tồn tại",
            code="DOCTOR_NOT_FOUND"
        )

    cache_key = f"catalog:slots:{doctor_id}:{slot_date or 'all'}:{page}:{limit}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    filters = [TimeSlot.doctor_id == doctor_id]
    if slot_date:
        start_of_day = datetime.combine(slot_date, time.min, tzinfo=timezone.utc)
        end_of_day = datetime.combine(slot_date, time.max, tzinfo=timezone.utc)
        filters.append(and_(TimeSlot.start_time >= start_of_day, TimeSlot.start_time <= end_of_day))

    count_stmt = select(func.count(TimeSlot.id)).where(*filters)
    total = (await db.execute(count_stmt)).scalar() or 0

    offset = (page - 1) * limit
    stmt = select(TimeSlot).where(*filters).order_by(TimeSlot.start_time).offset(offset).limit(limit)
    items = (await db.execute(stmt)).scalars().all()

    result = {
        "items": [SlotOut.model_validate(item).model_dump(mode="json") for item in items],
        "total": total,
        "page": page,
        "limit": limit
    }

    await set_cache(cache_key, result)
    return result


@router.post("/doctors/{doctor_id}/slots", response_model=SlotOut, status_code=status.HTTP_201_CREATED)
async def create_doctor_slot(
    doctor_id: str,
    body: SlotCreate,
    current_user: CurrentUser = Depends(require_role(["ADMIN"])),
    db: AsyncSession = Depends(get_db)
):
    # 1. Kiểm tra bác sĩ có tồn tại
    doc_stmt = select(Doctor).where(Doctor.id == doctor_id)
    doc = (await db.execute(doc_stmt)).scalar_one_or_none()
    if not doc:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bác sĩ không tồn tại",
            code="DOCTOR_NOT_FOUND"
        )

    # 2. Kiểm tra khoảng thời gian hợp lệ
    if body.start_time >= body.end_time:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Thời gian bắt đầu phải trước thời gian kết thúc",
            code="INVALID_TIME_RANGE"
        )

    # 3. Kiểm tra chồng lấn khung giờ (SRS FR-2.5)
    overlap_stmt = select(TimeSlot).where(
        and_(
            TimeSlot.doctor_id == doctor_id,
            TimeSlot.start_time < body.end_time,
            TimeSlot.end_time > body.start_time
        )
    )
    # first() thay cho scalar_one_or_none(): một bác sĩ có thể có nhiều khung
    # giờ chồng lấn (ví dụ 8:00-8:30 và 8:30-9:00) và khung mới 8:00-9:00
    # chồng lên cả hai. scalar_one_or_none() sẽ ném lỗi "multiple rows" và
    # biến thành 500 thay vì 409.
    existing_overlap = (await db.execute(overlap_stmt)).scalars().first()
    if existing_overlap:
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Khung giờ này bị chồng lấn với khung giờ đã có của bác sĩ",
            code="SLOT_OVERLAP"
        )

    slot = TimeSlot(
        doctor_id=doctor_id,
        start_time=body.start_time,
        end_time=body.end_time,
        is_available=True
    )
    db.add(slot)
    await db.commit()
    await db.refresh(slot)

    await invalidate_catalog_cache(f"catalog:slots:{doctor_id}:*")
    return slot
