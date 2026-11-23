"""Nap du lieu mau cho he thong dat lich kham.

Chay tu thu muc goc du an:
    python scripts/seed.py              # nap them, bo qua ban ghi da co
    python scripts/seed.py --reset      # xoa du lieu cu roi nap lai

Du lieu that: khoa va bac si trong data/*.csv (nguon ghi o data/SOURCES.md).
Du lieu mo phong: gia kham, khung gio, tai khoan thu nghiem, lich hen thu.

Script chay tren may lap trinh vien, ngoai mang Docker, nen host mac dinh la
localhost. Trong container phai dat ALEMBIC_DB_HOST=postgres.
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"

# Gio lam viec mo phong: sang 8:00-11:30, chieu 14:00-17:30, moi khung 30 phut.
MORNING_HOURS = (8, 9, 10)
AFTERNOON_HOURS = (14, 15, 16)
SLOT_MINUTES = 30
SLOT_DAYS = 5

TEST_PATIENTS = 10
TEST_APPOINTMENTS = 20

VN_TZ = timezone(timedelta(hours=7))


def database_url(env_name: str) -> str:
    """Doc chuoi ket noi cua mot service, bo phan driver cua SQLAlchemy.

    psycopg nhan thang "postgresql://", khong hieu hau to "+asyncpg"/"+psycopg".
    """
    url = os.getenv(env_name)
    if not url:
        raise RuntimeError(f"{env_name} chua duoc dat trong .env")

    url = url.replace("postgresql+asyncpg://", "postgresql://")
    url = url.replace("postgresql+psycopg://", "postgresql://")

    in_container = Path("/.dockerenv").exists()
    host = os.getenv("ALEMBIC_DB_HOST") or ("postgres" if in_container else "localhost")

    parts = urlsplit(url)
    port = parts.port or 5432
    userinfo = parts.netloc.rsplit("@", 1)[0] if "@" in parts.netloc else ""
    netloc = f"{userinfo}@{host}:{port}" if userinfo else f"{host}:{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def read_csv(name: str) -> list[dict[str, str]]:
    path = DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Khong thay {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def fake_password_hash() -> str:
    """Hash gia de tai khoan thu khong dang nhap duoc bang mat khau that.

    Khong import bcrypt: script chi can mot chuoi hop le, va tai khoan benh nhan
    duoc tao cho muc dich do tai, khong phai de dang nhap thu cong.
    """
    return "$2b$12$" + uuid.uuid4().hex[:53]


def reset(conns: dict[str, psycopg.Connection]) -> None:
    """Xoa du lieu theo thu tu phu thuoc khoa ngoai."""
    with conns["booking"].cursor() as cur:
        cur.execute("TRUNCATE appointments RESTART IDENTITY CASCADE")
    with conns["catalog"].cursor() as cur:
        cur.execute("TRUNCATE time_slots, doctors, departments RESTART IDENTITY CASCADE")
    with conns["auth"].cursor() as cur:
        cur.execute("TRUNCATE users RESTART IDENTITY CASCADE")


def seed_departments(conn: psycopg.Connection) -> dict[str, str]:
    """Tra ve map ten khoa -> id."""
    rows = read_csv("departments.csv")
    mapping: dict[str, str] = {}

    with conn.cursor() as cur:
        for row in rows:
            department_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO departments (id, name, description)
                VALUES (%s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description
                RETURNING id
                """,
                (department_id, row["name"], row.get("description") or None),
            )
            mapping[row["name"]] = cur.fetchone()[0]

    conn.commit()
    return mapping


def seed_doctors(conn: psycopg.Connection, departments: dict[str, str]) -> list[str]:
    rows = read_csv("doctors.csv")
    doctor_ids: list[str] = []

    with conn.cursor() as cur:
        for row in rows:
            dept_id = departments.get(row["department_name"])
            if dept_id is None:
                raise ValueError(f"Khoa khong ton tai: {row['department_name']}")

            # Khoa nay chua co rang buoc unique tren (full_name, department_id),
            # nen phai tu tra cuu de chay lai khong sinh ban ghi trung.
            cur.execute(
                """
                SELECT id FROM doctors
                WHERE full_name = %s AND department_id = %s
                LIMIT 1
                """,
                (row["full_name"], dept_id),
            )
            existing = cur.fetchone()
            if existing:
                doctor_ids.append(existing[0])
                continue

            cur.execute(
                """
                INSERT INTO doctors
                    (id, user_id, department_id, full_name, title, price, is_active)
                VALUES (%s, NULL, %s, %s, %s, %s, TRUE)
                RETURNING id
                """,
                (
                    str(uuid.uuid4()),
                    dept_id,
                    row["full_name"],
                    row["title"],
                    int(row["price"]),
                ),
            )
            doctor_ids.append(cur.fetchone()[0])

    conn.commit()
    return doctor_ids


def build_slot_times() -> list[tuple[datetime, datetime]]:
    """Sinh khung gio cho 5 ngay lam viec ke tiep, bo Thu Bay va Chu Nhat."""
    today = datetime.now(VN_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    result: list[tuple[datetime, datetime]] = []
    day = today
    workdays = 0

    while workdays < SLOT_DAYS:
        day += timedelta(days=1)
        if day.weekday() >= 5:
            continue
        workdays += 1
        for hour in MORNING_HOURS + AFTERNOON_HOURS:
            for minute in (0, SLOT_MINUTES):
                start = day.replace(hour=hour, minute=minute)
                end = start + timedelta(minutes=SLOT_MINUTES)
                result.append((start, end))

    return result


def seed_slots(conn: psycopg.Connection, doctor_ids: list[str]) -> list[tuple[str, str]]:
    """Tra ve danh sach (slot_id, doctor_id) de dung cho lich hen thu.

    Khung gio chua co rang buoc unique, nen kiem tra theo bac si: bac si nao
    da co khung gio thi bo qua, tranh chay lai sinh them hang nghin dong.
    """
    times = build_slot_times()
    slots: list[tuple[str, str]] = []

    with conn.cursor() as cur:
        for doctor_id in doctor_ids:
            cur.execute(
                "SELECT id FROM time_slots WHERE doctor_id = %s ORDER BY start_time",
                (doctor_id,),
            )
            existing = [row[0] for row in cur.fetchall()]
            if existing:
                slots.extend((slot_id, doctor_id) for slot_id in existing)
                continue

            for start, end in times:
                slot_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO time_slots
                        (id, doctor_id, start_time, end_time, is_available, created_at)
                    VALUES (%s, %s, %s, %s, TRUE, %s)
                    """,
                    (slot_id, doctor_id, start, end, datetime.now(timezone.utc)),
                )
                slots.append((slot_id, doctor_id))

    conn.commit()
    return slots


def seed_users(conn: psycopg.Connection) -> tuple[list[str], dict[str, str]]:
    """Tao 1 ADMIN, 1 DOCTOR mau va mot so benh nhan thu.

    Tra ve (danh sach patient_id, map email -> id).
    """
    now = datetime.now(timezone.utc)
    patients: list[str] = []
    by_email: dict[str, str] = {}

    accounts = [
        ("admin@example.com", "Quan Tri Vien", "ADMIN"),
        ("doctor@example.com", "Bac Si Mau", "DOCTOR"),
    ]
    accounts += [
        (f"patient{i:02d}@example.com", f"Benh Nhan Thu {i:02d}", "PATIENT")
        for i in range(1, TEST_PATIENTS + 1)
    ]

    with conn.cursor() as cur:
        for email, full_name, role in accounts:
            user_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO users
                    (id, email, hashed_password, full_name, role, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (email) DO NOTHING
                RETURNING id
                """,
                (user_id, email, fake_password_hash(), full_name, role, now, now),
            )
            created = cur.fetchone()
            if created is None:
                cur.execute("SELECT id FROM users WHERE email = %s", (email,))
                user_id = cur.fetchone()[0]
            else:
                user_id = created[0]

            by_email[email] = user_id
            if role == "PATIENT":
                patients.append(user_id)

    conn.commit()
    return patients, by_email


def seed_appointments(
    conn: psycopg.Connection,
    slots: list[tuple[str, str]],
    patients: list[str],
) -> int:
    """Tao lich hen thu tren cac khung gio con trong.

    Database la thu quyet dinh: unique partial index se tu choi neu mot khung
    gio da co lich CONFIRMED, va script bo qua dong do.
    """
    if not slots or not patients:
        return 0

    random.seed(20261124)  # cung du lieu moi lan chay --reset
    chosen = random.sample(slots, k=min(TEST_APPOINTMENTS, len(slots)))
    created = 0

    with conn.cursor() as cur:
        for slot_id, doctor_id in chosen:
            # Khung da co lich (CONFIRMED hoac CANCELLED) thi bo qua de chay
            # lai khong sinh ban ghi trung.
            cur.execute(
                "SELECT 1 FROM appointments WHERE slot_id = %s LIMIT 1",
                (slot_id,),
            )
            if cur.fetchone():
                continue

            # Gia lap mot phan lich da huy de du lieu co ca hai trang thai.
            status = "CANCELLED" if created % 5 == 0 else "CONFIRMED"
            cur.execute(
                """
                INSERT INTO appointments
                    (id, patient_id, doctor_id, slot_id, status, note)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    str(uuid.uuid4()),
                    random.choice(patients),
                    doctor_id,
                    slot_id,
                    status,
                    "Lich hen thu nghiem",
                ),
            )
            if cur.rowcount:
                created += 1

    conn.commit()
    return created


def clear_catalog_cache() -> None:
    """Xoa cache danh muc de giao dien thay du lieu vua nap.

    Catalog cache ket qua 5 phut; neu khong xoa, API van tra danh sach rong.
    Loi Redis khong lam hong viec nap du lieu, chi canh bao.
    """
    try:
        import redis
    except ImportError:
        print("  (bo qua: chua cai thu vien redis)")
        return

    url = os.getenv("REDIS_URL")
    if not url:
        return

    in_container = Path("/.dockerenv").exists()
    if not in_container:
        # .env dat host "redis" (ten service trong Compose); chay tren may
        # Windows phai doi sang localhost vi ten do chi phan giai trong mang Docker.
        parts = urlsplit(url)
        port = parts.port or 6379
        netloc = f"localhost:{port}"
        if parts.username:
            userinfo = parts.username + (f":{parts.password}" if parts.password else "")
            netloc = f"{userinfo}@{netloc}"
        url = urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))

    try:
        client = redis.from_url(url, socket_connect_timeout=2)
        keys = list(client.scan_iter("catalog:*"))
        if keys:
            client.delete(*keys)
        print(f"  da xoa {len(keys)} key cache")
    except Exception as exc:  # noqa: BLE001 - cache khong phai dieu kien bat buoc
        print(f"  (khong xoa duoc cache: {exc})")


def verify(conns: dict[str, psycopg.Connection]) -> dict[str, int]:
    result: dict[str, int] = {}
    queries = {
        "catalog": [
            ("departments", "SELECT count(*) FROM departments"),
            ("doctors", "SELECT count(*) FROM doctors"),
            ("time_slots", "SELECT count(*) FROM time_slots"),
        ],
        "auth": [("users", "SELECT count(*) FROM users")],
        "booking": [
            ("appointments", "SELECT count(*) FROM appointments"),
            ("confirmed", "SELECT count(*) FROM appointments WHERE status = 'CONFIRMED'"),
        ],
    }

    for name, statements in queries.items():
        with conns[name].cursor() as cur:
            for label, sql in statements:
                cur.execute(sql)
                result[label] = cur.fetchone()[0]

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Nap du lieu mau cho he thong.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Xoa du lieu cu truoc khi nap (chay lai nhieu lan khong nhan ban)",
    )
    args = parser.parse_args()

    conns = {
        "auth": psycopg.connect(database_url("AUTH_DB_URL"), autocommit=False),
        "catalog": psycopg.connect(database_url("CATALOG_DB_URL"), autocommit=False),
        "booking": psycopg.connect(database_url("BOOKING_DB_URL"), autocommit=False),
    }

    try:
        if args.reset:
            print("Xoa du lieu cu...")
            reset(conns)

        print("Nap khoa...")
        departments = seed_departments(conns["catalog"])
        print(f"  {len(departments)} khoa")

        print("Nap bac si...")
        doctor_ids = seed_doctors(conns["catalog"], departments)
        print(f"  {len(doctor_ids)} bac si")

        print("Nap khung gio...")
        slots = seed_slots(conns["catalog"], doctor_ids)
        print(f"  {len(slots)} khung gio")

        print("Nap tai khoan thu nghiem...")
        patients, _ = seed_users(conns["auth"])
        print(f"  {len(patients)} benh nhan + 1 bac si + 1 quan tri")

        print("Nap lich hen thu...")
        created = seed_appointments(conns["booking"], slots, patients)
        print(f"  {created} lich hen")

        print("Xoa cache danh muc...")
        clear_catalog_cache()

        print("\nKet qua trong database:")
        for label, count in verify(conns).items():
            print(f"  {label:12} {count}")

    finally:
        for conn in conns.values():
            conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
