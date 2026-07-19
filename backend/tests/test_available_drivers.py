"""GET /trips/meta/drivers/available — รายชื่อคนขับสำหรับฟอร์มจ่ายงาน

- ต้องคืนเฉพาะคนที่ "รองาน" (สีขาว) · คนที่กำลังวิ่ง (ORANGE/GREEN) ต้องหายไป
- waiting_type แยก 2 ประเภท: SUB_TRIP (เที่ยวหลักยังค้าง) / NEW_TRIP (ไม่มีเที่ยวค้าง)
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Drop, Trip, User
from app.models.enums import Role, TripStatus
from app.security import hash_password


def login(client, ident, pw="1234"):
    r = client.post("/auth/login", json={"identifier": ident, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def staff(db_session):
    db_session.add(
        User(emp_id="SV01", name="ธนพล คุมงาน", phone="0820000001",
             role=Role.SUPERVISOR, active=True, password_hash=hash_password("1234"))
    )
    db_session.commit()
    return db_session


def _trip(db, emp_id, code, status, *, completed=False, n_drops=1, assigned=True):
    drv = db.query(User).filter(User.emp_id == emp_id).first()
    now = datetime.now(timezone.utc)
    t = Trip(code=code, driver_id=drv.id, status=status, distance_km=10, plate="1กก1234",
             assigned_at=now if assigned else None,
             completed_at=now if completed else None,
             closed_at=now if completed else None)
    db.add(t)
    db.commit()
    db.refresh(t)
    for i in range(1, n_drops + 1):
        db.add(Drop(trip_id=t.id, seq=i, name=f"จุด{i}", allowance=100,
                    origin=f"ต้นทาง{i}", destination=f"ปลายทาง{i}"))
    db.commit()
    db.refresh(t)
    return t


def _rows(client, staff):
    return client.get("/trips/meta/drivers/available", headers=login(client, "SV01")).json()


def test_busy_driver_excluded(client, staff):
    """คนขับที่กำลังวิ่ง (GREEN) ต้องไม่ถูกส่งมาให้เลือก"""
    _trip(staff, "D01", "T-AV1", TripStatus.GREEN)
    emp_ids = [r["emp_id"] for r in _rows(client, staff)]
    assert "D01" not in emp_ids


def test_orange_driver_excluded(client, staff):
    _trip(staff, "D01", "T-AV2", TripStatus.ORANGE)
    assert "D01" not in [r["emp_id"] for r in _rows(client, staff)]


def test_idle_with_active_main_trip_is_sub_trip(client, staff):
    """ว่าง (WHITE) แต่เที่ยวหลักยังไม่จบ → SUB_TRIP พร้อมข้อมูลเที่ยวเดิม"""
    t = _trip(staff, "D01", "T-AV3", TripStatus.WHITE, n_drops=2)
    row = next(r for r in _rows(client, staff) if r["emp_id"] == "D01")
    assert row["waiting_type"] == "SUB_TRIP"
    assert row["active_trip_id"] == t.id
    assert row["active_trip_code"] == "T-AV3"
    assert row["active_trip_drops"] == 2


def test_completed_trip_driver_is_new_trip(client, staff):
    """เที่ยวหลักจบแล้ว → NEW_TRIP (ไม่มีเที่ยวค้าง)"""
    _trip(staff, "D01", "T-AV4", TripStatus.WHITE, completed=True)
    row = next(r for r in _rows(client, staff) if r["emp_id"] == "D01")
    assert row["waiting_type"] == "NEW_TRIP"
    assert row["active_trip_id"] is None


def test_driver_without_any_trip_is_new_trip(client, staff):
    """ไม่มีทริปเลย → NEW_TRIP"""
    row = next(r for r in _rows(client, staff) if r["emp_id"] == "D01")
    assert row["waiting_type"] == "NEW_TRIP"
    assert row["active_trip_code"] is None


def test_unassigned_trip_does_not_count_as_active(client, staff):
    """ทริปที่สร้างไว้แต่ยังไม่จ่ายงาน (ไม่มี assigned_at) ไม่นับเป็นเที่ยวหลักค้าง"""
    _trip(staff, "D01", "T-AV5", TripStatus.WHITE, assigned=False)
    row = next(r for r in _rows(client, staff) if r["emp_id"] == "D01")
    assert row["waiting_type"] == "NEW_TRIP"


def test_driver_forbidden(client, staff):
    assert client.get("/trips/meta/drivers/available",
                      headers=login(client, "D01")).status_code == 403
