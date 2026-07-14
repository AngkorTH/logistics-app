"""Integration tests: จบงานอัตโนมัติ + กล่องจดหมายแจ้งเตือน
- ส่งครบทุกจุด → WHITE อัตโนมัติ (ยังไม่ freeze) · บิลไม่บังคับ
- คนคุมยังตรวจ/อนุมัติบิลได้หลังจบงาน (ยังไม่ล็อก)
- แจ้งเตือน BILL_UPLOADED เมื่ออัปบิล · TRIP_DONE เมื่อจบงาน
- Notification inbox RBAC (Driver 403) + mark read
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Drop, Notification, Trip, User
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


def _green_trip(db, code="T-AC", n=2):
    """ทริปพร้อมส่งของ (GREEN) มี n จุด"""
    d01 = db.query(User).filter(User.emp_id == "D01").first()
    trip = Trip(code=code, driver_id=d01.id, status=TripStatus.GREEN, distance_km=50,
                plate="1กก1234", assigned_at=datetime.now(timezone.utc),
                finished_loading_at=datetime.now(timezone.utc))
    db.add(trip)
    db.commit()
    db.refresh(trip)
    for i in range(1, n + 1):
        db.add(Drop(trip_id=trip.id, seq=i, name=f"จุด{i}", allowance=300))
    db.commit()
    db.refresh(trip)
    return trip


# =========================== Auto-complete ===========================
def test_partial_delivery_stays_green(client, staff):
    trip = _green_trip(staff, "T-AC1", n=2)
    drv = login(client, "D01")
    r = client.post(f"/drops/{trip.drops[0].id}/delivery", json={"lat": 13.8, "lng": 100.6}, headers=drv)
    assert r.status_code == 200
    # ส่งแค่จุดเดียว → ทริปยังไม่จบ (GREEN)
    staff.refresh(trip)
    assert trip.status is TripStatus.GREEN


def test_full_delivery_auto_completes_white_not_frozen(client, staff):
    """ส่งครบทุกจุด → WHITE อัตโนมัติ · closed_at set · ยังไม่ freeze · ไม่ต้องมีบิล"""
    trip = _green_trip(staff, "T-AC2", n=2)
    drv = login(client, "D01")
    for d in trip.drops:
        assert client.post(f"/drops/{d.id}/delivery", json={"lat": 13.8, "lng": 100.6}, headers=drv).status_code == 200
    staff.refresh(trip)
    assert trip.status is TripStatus.WHITE
    assert trip.closed_at is not None
    assert trip.frozen is False   # บิลยังตรวจได้ทีหลัง


def test_bills_reviewable_after_auto_complete(client, staff):
    """หลังจบงานอัตโนมัติ (ยังไม่ล็อก) คนคุมยังอนุมัติบิลได้"""
    trip = _green_trip(staff, "T-AC3", n=1)
    drv = login(client, "D01")
    sv = login(client, "SV01")
    # อัปบิลก่อนส่ง
    r = client.post(f"/drops/{trip.drops[0].id}/receipt", json={"kind": "FUEL", "ocr_amount": 800}, headers=drv)
    rid = r.json()["id"]
    # ส่งครบ → auto WHITE
    client.post(f"/drops/{trip.drops[0].id}/delivery", json={"lat": 13.8, "lng": 100.6}, headers=drv)
    staff.refresh(trip)
    assert trip.status is TripStatus.WHITE and trip.frozen is False
    # ยังอนุมัติบิลได้ (ไม่ freeze)
    assert client.post(f"/receipts/{rid}/approve", json={}, headers=sv).status_code == 200
    # แล้วคนคุมล็อกการเงิน → freeze
    r = client.post(f"/trips/{trip.id}/close", headers=sv)
    assert r.status_code == 200 and r.json()["frozen"] is True


def test_dispatch_queue_reflects_completion(client, staff):
    """คิวงานต้องย้ายคนขับจาก green → white เมื่อส่งของครบ (state ตรงกับหน้าคนขับ)"""
    trip = _green_trip(staff, "T-Q1", n=2)
    sv = login(client, "SV01")
    drv = login(client, "D01")
    # ก่อนส่ง: D01 อยู่กลุ่ม green
    q = client.get("/dispatch/queue", headers=sv).json()
    assert "D01" in [x["emp_id"] for x in q["green"]]
    # ส่งครบทุกจุด
    for d in trip.drops:
        client.post(f"/drops/{d.id}/delivery", json={"lat": 13.8, "lng": 100.6}, headers=drv)
    # หลังส่งครบ: D01 ต้องย้ายไป white ไม่ค้างที่ green
    q2 = client.get("/dispatch/queue", headers=sv).json()
    assert "D01" in [x["emp_id"] for x in q2["white"]]
    assert "D01" not in [x["emp_id"] for x in q2["green"]]


# =========================== Notifications ===========================
def test_bill_upload_creates_notification(client, staff):
    trip = _green_trip(staff, "T-AC4", n=1)
    drv = login(client, "D01")
    client.post(f"/drops/{trip.drops[0].id}/receipt", json={"kind": "FUEL", "ocr_amount": 500}, headers=drv)
    rows = client.get("/notifications", headers=login(client, "SV01")).json()
    assert any(n["kind"] == "BILL_UPLOADED" and n["trip_id"] == trip.id for n in rows)


def test_auto_complete_creates_notification(client, staff):
    trip = _green_trip(staff, "T-AC5", n=1)
    drv = login(client, "D01")
    client.post(f"/drops/{trip.drops[0].id}/delivery", json={"lat": 13.8, "lng": 100.6}, headers=drv)
    rows = client.get("/notifications", headers=login(client, "SV01")).json()
    assert any(n["kind"] == "TRIP_DONE" and n["trip_id"] == trip.id for n in rows)


def test_notifications_driver_forbidden(client, staff):
    assert client.get("/notifications", headers=login(client, "D01")).status_code == 403


# =========================== Unfreeze (ปลดล็อกเพื่อแก้ไข) ===========================
def _frozen_trip(client, staff):
    """ทริปที่จบงาน + ล็อกการเงินแล้ว (frozen)"""
    trip = _green_trip(staff, "T-UF", n=1)
    drv = login(client, "D01")
    sv = login(client, "SV01")
    client.post(f"/drops/{trip.drops[0].id}/delivery", json={"lat": 13.8, "lng": 100.6}, headers=drv)
    client.post(f"/trips/{trip.id}/close", headers=sv)   # ล็อกการเงิน
    staff.refresh(trip)
    assert trip.frozen is True
    return trip


def test_frozen_is_view_only_until_unfreeze(client, staff):
    """ทริป freeze แล้วแก้ไม่ได้ (ดูอย่างเดียว) จนกว่าจะปลดล็อก"""
    trip = _frozen_trip(client, staff)
    sv = login(client, "SV01")
    # แก้ยอดหักตอน freeze → 400
    assert client.patch(f"/trips/{trip.id}/adjust",
                        json={"edit_reason": "x", "bonus": 50}, headers=sv).status_code == 400
    # ปลดล็อกไม่ใส่เหตุผล → 422
    assert client.post(f"/trips/{trip.id}/unfreeze", json={}, headers=sv).status_code == 422
    # ปลดล็อก (มีเหตุผล) → 200 + frozen False + แจ้งเตือน
    r = client.post(f"/trips/{trip.id}/unfreeze", json={"reason": "แก้ยอดบิลผิด"}, headers=sv)
    assert r.status_code == 200 and r.json()["frozen"] is False
    # ปลดแล้วแก้ได้
    assert client.patch(f"/trips/{trip.id}/adjust",
                        json={"edit_reason": "ปรับโบนัส", "bonus": 50}, headers=sv).status_code == 200
    # มีแจ้งเตือน TRIP_UNFROZEN
    rows = client.get("/notifications", headers=sv).json()
    assert any(n["kind"] == "TRIP_UNFROZEN" and n["trip_id"] == trip.id for n in rows)


def test_unfreeze_driver_forbidden(client, staff):
    trip = _frozen_trip(client, staff)
    assert client.post(f"/trips/{trip.id}/unfreeze",
                       json={"reason": "x"}, headers=login(client, "D01")).status_code == 403


def test_unfreeze_non_frozen_400(client, staff):
    trip = _green_trip(staff, "T-UF2", n=1)  # ยังไม่ freeze
    sv = login(client, "SV01")
    assert client.post(f"/trips/{trip.id}/unfreeze", json={"reason": "x"}, headers=sv).status_code == 400


def test_notification_mark_read(client, staff):
    db = staff
    db.add(Notification(kind="BILL_UPLOADED", title="x", message="y"))
    db.commit()
    sv = login(client, "SV01")
    unread = client.get("/notifications?unread=true", headers=sv).json()
    assert len(unread) >= 1
    nid = unread[0]["id"]
    assert client.post(f"/notifications/{nid}/read", headers=sv).json()["read"] is True
    # อ่านแล้วไม่โผล่ใน unread
    assert all(n["id"] != nid for n in client.get("/notifications?unread=true", headers=sv).json())
