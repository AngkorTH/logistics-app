"""Integration tests: Management Suite (Step 2)

ครอบคลุม: Smart Dispatch Queue (การจัดกลุ่ม+เรียงลำดับ), Penalty (หลายรายการ),
User Management + Rating, Monthly History, Vehicle Assignment
เน้นย้ำ RBAC: Driver ต้องโดน 403 ทุก endpoint ชุดนี้
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Trip, User, Vehicle
from app.models.enums import Role, TripDifficulty, TripStatus
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
    """เพิ่ม supervisor + super_admin (นอกเหนือจาก AD01 admin ใน conftest)"""
    db = db_session
    db.add_all([
        User(emp_id="SV01", name="ธนพล คุมงาน", phone="0820000001",
             role=Role.SUPERVISOR, active=True, password_hash=hash_password("1234")),
        User(emp_id="SA01", name="ใหญ่ สุดยอด", phone="0840000001",
             role=Role.SUPER_ADMIN, active=True, password_hash=hash_password("1234")),
    ])
    db.commit()
    return db


def _closed_trip(db, driver, difficulty, load_seconds, code):
    """สร้างทริปที่ปิดงานแล้ว (สำหรับทดสอบ dispatch metric)"""
    now = datetime.now(timezone.utc)
    trip = Trip(
        code=code, driver_id=driver.id, status=TripStatus.WHITE,
        difficulty=difficulty, distance_km=100,
        assigned_at=now - timedelta(seconds=load_seconds + 100),
        finished_loading_at=now - timedelta(seconds=100),
        closed_at=now, frozen=True,
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


# =========================== Smart Dispatch Queue ===========================
def test_dispatch_driver_forbidden(client, staff):
    """Driver เรียกคิวจ่ายงานไม่ได้ → 403"""
    h = login(client, "D01")
    assert client.get("/dispatch/queue", headers=h).status_code == 403


def test_dispatch_requires_token(client, staff):
    assert client.get("/dispatch/queue").status_code == 401


def test_dispatch_grouping_and_sorting(client, staff):
    """จัดกลุ่ม 3 สี + เรียง White: HARD ก่อน → ไวก่อน → ดาวมากก่อน"""
    db = staff
    # เตรียมคนขับ 4 คน
    d_hard = User(emp_id="DH", name="หนักมา", phone="0811111111",
                  role=Role.DRIVER, active=True, rating=1, password_hash=hash_password("1234"))
    d_fast = User(emp_id="DF", name="ไวมาก", phone="0822222222",
                  role=Role.DRIVER, active=True, rating=2, password_hash=hash_password("1234"))
    d_slow = User(emp_id="DS", name="ช้าหน่อย", phone="0833333333",
                  role=Role.DRIVER, active=True, rating=5, password_hash=hash_password("1234"))
    d_busy = User(emp_id="DB", name="ติดงาน", phone="0844444444",
                  role=Role.DRIVER, active=True, password_hash=hash_password("1234"))
    db.add_all([d_hard, d_fast, d_slow, d_busy])
    db.commit()
    for u in (d_hard, d_fast, d_slow, d_busy):
        db.refresh(u)

    # ทริปก่อนหน้า (ปิดแล้ว)
    _closed_trip(db, d_hard, TripDifficulty.HARD, 200, "T-H")
    _closed_trip(db, d_fast, TripDifficulty.MEDIUM, 60, "T-F")
    _closed_trip(db, d_slow, TripDifficulty.MEDIUM, 300, "T-S")
    # d_busy กำลังติดงาน ORANGE
    db.add(Trip(code="T-B", driver_id=d_busy.id, status=TripStatus.ORANGE,
                difficulty=TripDifficulty.EASY, distance_km=50,
                assigned_at=datetime.now(timezone.utc)))
    db.commit()

    h = login(client, "SV01")
    r = client.get("/dispatch/queue", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()

    # d_busy อยู่กลุ่ม orange ไม่อยู่ white
    assert [d["emp_id"] for d in data["orange"]] == ["DB"]

    white_order = [d["emp_id"] for d in data["white"]]
    # D01 (จาก conftest) ไม่มีทริปก่อนหน้า → ท้ายสุด
    assert white_order[:3] == ["DH", "DF", "DS"]
    assert white_order[-1] == "D01"
    # ดาวส่งออกมาเป็นตัวเลขให้ frontend เรนเดอร์ดาว
    assert data["white"][0]["rating"] == 1


# =========================== Penalty (หลายรายการ) ===========================
@pytest.fixture()
def trip_with_drops(db_session):
    d01 = db_session.query(User).filter(User.emp_id == "D01").first()
    trip = Trip(code="T-P1", driver_id=d01.id, status=TripStatus.GREEN, distance_km=80)
    db_session.add(trip)
    db_session.commit()
    db_session.refresh(trip)
    from app.models import Drop
    db_session.add_all([
        Drop(trip_id=trip.id, seq=1, name="A", allowance=300),
        Drop(trip_id=trip.id, seq=2, name="B", allowance=200),
    ])
    db_session.commit()
    db_session.refresh(trip)
    return trip


def test_penalty_driver_forbidden(client, staff, trip_with_drops):
    h = login(client, "D01")
    r = client.post(f"/trips/{trip_with_drops.id}/penalties",
                    json={"amount": 50, "reason": "x"}, headers=h)
    assert r.status_code == 403


def test_penalty_create_and_list(client, staff, trip_with_drops):
    tid = trip_with_drops.id
    sv = login(client, "SV01")
    # เหตุผลว่าง → 422 (schema)
    assert client.post(f"/trips/{tid}/penalties",
                       json={"amount": 50, "reason": ""}, headers=sv).status_code == 422
    # เพิ่ม 2 รายการ
    assert client.post(f"/trips/{tid}/penalties",
                       json={"amount": 100, "reason": "ไม่คลุมผ้าใบ"}, headers=sv).status_code == 200
    assert client.post(f"/trips/{tid}/penalties",
                       json={"amount": 150, "reason": "ส่งช้า"}, headers=sv).status_code == 200
    # หักเกินเบี้ยเลี้ยงรวม (500) → 400
    assert client.post(f"/trips/{tid}/penalties",
                       json={"amount": 999, "reason": "เยอะ"}, headers=sv).status_code == 400

    # list ของทริป
    rows = client.get(f"/trips/{tid}/penalties", headers=sv).json()
    assert len(rows) == 2
    # list รวมทั้งระบบ (dashboard) — มีชื่อคนขับ + code
    allrows = client.get("/penalties", headers=sv).json()
    assert len(allrows) == 2
    assert allrows[0]["driver_name"] == "สมชาย ใจดี"
    assert allrows[0]["trip_code"] == "T-P1"

    # finance สะท้อนยอดหักรวม 250
    fin = client.get(f"/trips/{tid}/finance", headers=sv).json()
    assert fin["allowance_net"] == 250  # 500 - 250


def test_penalty_list_driver_forbidden(client, staff):
    h = login(client, "D01")
    assert client.get("/penalties", headers=h).status_code == 403


# =========================== User Management + Rating ===========================
def test_user_list_requires_admin(client, staff):
    """Supervisor แก้/ดูพนักงานไม่ได้ (ต้อง Admin+) · Driver ยิ่งไม่ได้"""
    assert client.get("/users", headers=login(client, "D01")).status_code == 403
    assert client.get("/users", headers=login(client, "SV01")).status_code == 403
    assert client.get("/users", headers=login(client, "AD01")).status_code == 200


def test_edit_user(client, staff):
    ad = login(client, "AD01")
    d01 = staff.query(User).filter(User.emp_id == "D01").first()
    r = client.patch(f"/users/{d01.id}", json={"name": "สมชาย เปลี่ยนชื่อ"}, headers=ad)
    assert r.status_code == 200 and r.json()["name"] == "สมชาย เปลี่ยนชื่อ"


def test_edit_user_driver_forbidden(client, staff):
    d01 = staff.query(User).filter(User.emp_id == "D01").first()
    h = login(client, "D01")
    assert client.patch(f"/users/{d01.id}", json={"name": "แอบแก้"}, headers=h).status_code == 403


def test_rate_driver(client, staff):
    ad = login(client, "AD01")
    d01 = staff.query(User).filter(User.emp_id == "D01").first()
    r = client.post(f"/users/{d01.id}/rating", json={"rating": 4}, headers=ad)
    assert r.status_code == 200 and r.json()["rating"] == 4
    # ดาวเกิน 5 → 422
    assert client.post(f"/users/{d01.id}/rating", json={"rating": 9}, headers=ad).status_code == 422
    # supervisor ให้ดาวไม่ได้ (ต้อง Admin+)
    assert client.post(f"/users/{d01.id}/rating", json={"rating": 3},
                       headers=login(client, "SV01")).status_code == 403


# =========================== Monthly History ===========================
def test_monthly_history_rbac_and_data(client, staff):
    db = staff
    d01 = db.query(User).filter(User.emp_id == "D01").first()
    _closed_trip(db, d01, TripDifficulty.EASY, 120, "T-M1")
    _closed_trip(db, d01, TripDifficulty.HARD, 90, "T-M2")

    # Driver ดูไม่ได้
    assert client.get(f"/users/{d01.id}/history/monthly",
                      headers=login(client, "D01")).status_code == 403
    # Supervisor ดูได้
    r = client.get(f"/users/{d01.id}/history/monthly", headers=login(client, "SV01"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["driver_id"] == d01.id
    assert sum(m["trips"] for m in body["months"]) == 2


# =========================== Vehicle Assignment ===========================
def test_vehicle_crud_and_assign(client, staff):
    ad = login(client, "AD01")
    # เพิ่มรถ
    r = client.post("/vehicles", json={"plate": "1กก1111", "model": "ISUZU"}, headers=ad)
    assert r.status_code == 200, r.text
    vid = r.json()["id"]
    # ทะเบียนซ้ำ → 400
    assert client.post("/vehicles", json={"plate": "1กก1111"}, headers=ad).status_code == 400
    # ผูกคนขับ D01
    d01 = staff.query(User).filter(User.emp_id == "D01").first()
    r = client.post(f"/vehicles/{vid}/assign", json={"driver_id": d01.id}, headers=ad)
    assert r.status_code == 200 and r.json()["driver_id"] == d01.id
    # ถอดคนขับ
    r = client.post(f"/vehicles/{vid}/assign", json={"driver_id": None}, headers=ad)
    assert r.json()["driver_id"] is None


def test_vehicle_rbac(client, staff):
    """Driver + Supervisor เข้าคลังรถไม่ได้ (require_admin)"""
    assert client.get("/vehicles", headers=login(client, "D01")).status_code == 403
    assert client.get("/vehicles", headers=login(client, "SV01")).status_code == 403
    assert client.get("/vehicles", headers=login(client, "AD01")).status_code == 200
