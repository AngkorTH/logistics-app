"""Integration tests: Layout Refactor & Trip Adjustment (claude.md ข้อ 6)

ครอบคลุม:
- Dispatch Queue: active trip fields + ค้นหา ?q= (ชื่อ/ทะเบียน)
- Penalty history: กรอง driver_name / month / year
- Trip Adjustment: PATCH /trips/{id}/adjust บังคับ edit_reason + audit + RBAC
- Monthly history flow: ?year=&month= คืนตารางทริปรายเที่ยว
เน้น RBAC: Driver ต้องโดน 403 ทุก endpoint
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Drop, Trip, User
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
    db_session.add(
        User(emp_id="SV01", name="ธนพล คุมงาน", phone="0820000001",
             role=Role.SUPERVISOR, active=True, password_hash=hash_password("1234"))
    )
    db_session.commit()
    return db_session


def _drops(db, trip, allowances):
    for i, a in enumerate(allowances, start=1):
        db.add(Drop(trip_id=trip.id, seq=i, name=f"จุด{i}", allowance=a))
    db.commit()


# =========================== Dispatch Queue search + active trip ===========================
def test_dispatch_active_trip_and_search(client, staff):
    db = staff
    d01 = db.query(User).filter(User.emp_id == "D01").first()
    # ทริปกำลังวิ่ง ORANGE + ผูกทะเบียน
    trip = Trip(code="T-ACT", driver_id=d01.id, status=TripStatus.ORANGE,
                plate="1กก1234", difficulty=TripDifficulty.EASY, distance_km=40,
                assigned_at=datetime.now(timezone.utc))
    db.add(trip)
    db.commit()
    db.refresh(trip)

    h = login(client, "SV01")
    data = client.get("/dispatch/queue", headers=h).json()
    orange = data["orange"]
    assert len(orange) == 1
    assert orange[0]["active_trip_id"] == trip.id
    assert orange[0]["active_trip_code"] == "T-ACT"
    assert orange[0]["plate"] == "1กก1234"

    # ค้นด้วยทะเบียน → เจอเฉพาะ d01
    r = client.get("/dispatch/queue?q=1234", headers=h).json()
    assert [d["emp_id"] for d in r["orange"]] == ["D01"]
    assert r["white"] == []
    # ค้นด้วยชื่อคนขับ
    r2 = client.get("/dispatch/queue?q=สมชาย", headers=h).json()
    assert r2["orange"][0]["emp_id"] == "D01"
    # ค้นไม่เจอ
    r3 = client.get("/dispatch/queue?q=ไม่มีจริง", headers=h).json()
    assert r3["orange"] == [] and r3["white"] == []


def test_dispatch_search_driver_forbidden(client, staff):
    assert client.get("/dispatch/queue?q=x", headers=login(client, "D01")).status_code == 403


# =========================== Penalty history filter ===========================
def test_penalty_filter_by_name_month_year(client, staff):
    db = staff
    d01 = db.query(User).filter(User.emp_id == "D01").first()
    trip = Trip(code="T-PF", driver_id=d01.id, status=TripStatus.GREEN, distance_km=50)
    db.add(trip)
    db.commit()
    db.refresh(trip)
    _drops(db, trip, [300, 200])

    sv = login(client, "SV01")
    assert client.post(f"/trips/{trip.id}/penalties",
                       json={"amount": 100, "reason": "สาย"}, headers=sv).status_code == 200

    now = datetime.now(timezone.utc)
    # ตรงชื่อ + เดือน/ปีปัจจุบัน → เจอ
    rows = client.get(f"/penalties?driver_name=สมชาย&month={now.month}&year={now.year}",
                      headers=sv).json()
    assert len(rows) == 1 and rows[0]["driver_name"] == "สมชาย ใจดี"
    # ชื่อไม่ตรง → ว่าง
    assert client.get("/penalties?driver_name=ไม่มีคนนี้", headers=sv).json() == []
    # ปีไม่ตรง → ว่าง
    assert client.get(f"/penalties?year={now.year - 1}", headers=sv).json() == []
    # เดือน invalid → 422
    assert client.get("/penalties?month=13", headers=sv).status_code == 422


# =========================== Trip Adjustment + edit_reason ===========================
@pytest.fixture()
def adj_trip(staff):
    db = staff
    d01 = db.query(User).filter(User.emp_id == "D01").first()
    trip = Trip(code="T-ADJ", driver_id=d01.id, status=TripStatus.GREEN, distance_km=100,
                difficulty=TripDifficulty.MEDIUM)
    db.add(trip)
    db.commit()
    db.refresh(trip)
    _drops(db, trip, [300, 200])
    return trip


def test_adjust_requires_edit_reason(client, adj_trip):
    sv = login(client, "SV01")
    # ไม่ส่ง edit_reason → 422 (schema บังคับ)
    assert client.patch(f"/trips/{adj_trip.id}/adjust",
                        json={"distance_km": 120}, headers=sv).status_code == 422
    # edit_reason ว่าง → 422
    assert client.patch(f"/trips/{adj_trip.id}/adjust",
                        json={"distance_km": 120, "edit_reason": ""}, headers=sv).status_code == 422


def test_adjust_driver_forbidden(client, adj_trip):
    h = login(client, "D01")
    r = client.patch(f"/trips/{adj_trip.id}/adjust",
                     json={"distance_km": 120, "edit_reason": "x"}, headers=h)
    assert r.status_code == 403


def test_adjust_fields_and_audit(client, staff, adj_trip):
    db = staff
    sv = login(client, "SV01")
    r = client.patch(f"/trips/{adj_trip.id}/adjust", headers=sv, json={
        "edit_reason": "ลูกค้าแจ้งระยะทางคลาดเคลื่อน",
        "distance_km": 150,
        "difficulty": "HARD",
        "penalty": 100,
        "penalty_reason": "ส่งช้า",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["distance_km"] == 150
    assert body["difficulty"] == "HARD"
    assert body["finance"]["allowance_net"] == 400  # 500 - 100

    # audit บันทึกเหตุผลไว้
    from app.models import AuditLog
    log = (db.query(AuditLog)
             .filter(AuditLog.action == "แก้ไขข้อมูลทริป")
             .order_by(AuditLog.id.desc()).first())
    assert log is not None and "ลูกค้าแจ้งระยะทางคลาดเคลื่อน" in log.detail


def test_adjust_penalty_requires_reason_and_ceiling(client, adj_trip):
    sv = login(client, "SV01")
    tid = adj_trip.id
    # แก้ penalty แต่ไม่ใส่เหตุผลหัก → 400
    assert client.patch(f"/trips/{tid}/adjust",
                        json={"edit_reason": "แก้", "penalty": 50}, headers=sv).status_code == 400
    # หักเกินเบี้ยเลี้ยงรวม (500) → 400
    assert client.patch(f"/trips/{tid}/adjust",
                        json={"edit_reason": "แก้", "penalty": 999,
                              "penalty_reason": "เยอะ"}, headers=sv).status_code == 400


def test_adjust_frozen_blocked(client, staff, adj_trip):
    db = staff
    adj_trip.frozen = True
    db.commit()
    sv = login(client, "SV01")
    r = client.patch(f"/trips/{adj_trip.id}/adjust",
                     json={"edit_reason": "แก้", "distance_km": 10}, headers=sv)
    assert r.status_code == 400 and "ล็อก" in r.json()["detail"]


# =========================== Monthly history flow ===========================
def test_monthly_history_with_month_year(client, staff):
    db = staff
    d01 = db.query(User).filter(User.emp_id == "D01").first()
    now = datetime.now(timezone.utc)
    trip = Trip(code="T-H1", driver_id=d01.id, status=TripStatus.WHITE,
                difficulty=TripDifficulty.HARD, distance_km=80,
                closed_at=now, frozen=True)
    db.add(trip)
    db.commit()
    db.refresh(trip)
    _drops(db, trip, [300])

    sv = login(client, "SV01")
    # ไม่ส่ง param → trips ว่าง (สรุปรายเดือนเท่านั้น)
    b0 = client.get(f"/users/{d01.id}/history/monthly", headers=sv).json()
    assert b0["trips"] == [] and sum(m["trips"] for m in b0["months"]) == 1
    # ส่ง year+month ปัจจุบัน → ได้ตารางรายเที่ยว
    b1 = client.get(f"/users/{d01.id}/history/monthly?year={now.year}&month={now.month}",
                    headers=sv).json()
    assert len(b1["trips"]) == 1
    assert b1["trips"][0]["code"] == "T-H1"
    assert b1["trips"][0]["difficulty"] == "HARD"
    # เดือนอื่น → ว่าง
    other = 1 if now.month != 1 else 2
    b2 = client.get(f"/users/{d01.id}/history/monthly?year={now.year}&month={other}",
                    headers=sv).json()
    assert b2["trips"] == []
