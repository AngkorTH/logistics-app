"""Integration tests: 5 งานรอบใหม่
- task 1: Manual status override + notification + audit
- task 2: Manual edit OCR receipt amount (บังคับ reason) + audit
- task 3: Deduction leaderboard (group by driver, sort desc)
- task 5: Audit Log read API (Admin+ เท่านั้น)
เน้น RBAC: Driver 403 · reason บังคับ · audit ถูกบันทึก
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import AuditLog, Drop, Penalty, Trip, User
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


def _trip(db, code, status=TripStatus.ORANGE, allowances=(300, 200)):
    d01 = db.query(User).filter(User.emp_id == "D01").first()
    trip = Trip(code=code, driver_id=d01.id, status=status, distance_km=50,
                assigned_at=datetime.now(timezone.utc))
    db.add(trip)
    db.commit()
    db.refresh(trip)
    for i, a in enumerate(allowances, start=1):
        db.add(Drop(trip_id=trip.id, seq=i, name=f"จุด{i}", allowance=a))
    db.commit()
    db.refresh(trip)
    return trip


# =========================== task 1: Status Override ===========================
def test_override_status_requires_reason(client, staff):
    trip = _trip(staff, "T-OV1")
    sv = login(client, "SV01")
    # ไม่ส่ง reason → 422
    assert client.post(f"/trips/{trip.id}/override-status",
                       json={"status": "GREEN"}, headers=sv).status_code == 422
    # reason ว่าง → 422
    assert client.post(f"/trips/{trip.id}/override-status",
                       json={"status": "GREEN", "reason": ""}, headers=sv).status_code == 422


def test_override_status_driver_forbidden(client, staff):
    trip = _trip(staff, "T-OV2")
    h = login(client, "D01")
    r = client.post(f"/trips/{trip.id}/override-status",
                    json={"status": "GREEN", "reason": "x"}, headers=h)
    assert r.status_code == 403


def test_override_status_success_and_audit(client, staff):
    db = staff
    trip = _trip(db, "T-OV3", status=TripStatus.ORANGE)
    sv = login(client, "SV01")
    r = client.post(f"/trips/{trip.id}/override-status",
                    json={"status": "GREEN", "reason": "คนขับลืมกดขึ้นของ"}, headers=sv)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "GREEN"
    log = (db.query(AuditLog).filter(AuditLog.action == "เปลี่ยนสถานะ (Manual Override)")
             .order_by(AuditLog.id.desc()).first())
    assert log is not None and "คนขับลืมกดขึ้นของ" in log.detail


# =========================== task 2: Edit OCR amount ===========================
@pytest.fixture()
def receipt(staff):
    """สร้างบิล OCR draft ผ่าน endpoint จริง"""
    return staff


def _make_receipt(client, db, headers):
    trip = _trip(db, "T-RC1", status=TripStatus.GREEN)
    drop = trip.drops[0]
    r = client.post(f"/drops/{drop.id}/receipt",
                    json={"kind": "FUEL", "ocr_amount": 500}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_edit_receipt_amount_requires_reason(client, staff):
    sv = login(client, "SV01")
    rid = _make_receipt(client, staff, sv)
    # ไม่ส่ง reason → 422
    assert client.patch(f"/receipts/{rid}/amount",
                        json={"new_amount": 600}, headers=sv).status_code == 422
    # reason ว่าง → 422
    assert client.patch(f"/receipts/{rid}/amount",
                        json={"new_amount": 600, "reason": ""}, headers=sv).status_code == 422


def test_edit_receipt_amount_success_and_audit(client, staff):
    db = staff
    sv = login(client, "SV01")
    rid = _make_receipt(client, db, sv)
    r = client.patch(f"/receipts/{rid}/amount",
                     json={"new_amount": 650, "reason": "OCR อ่านผิด บิลจริง 650"}, headers=sv)
    assert r.status_code == 200, r.text
    assert r.json()["amount"] == 650
    log = (db.query(AuditLog).filter(AuditLog.action == "แก้ยอดเงินใบเสร็จ (OCR)")
             .order_by(AuditLog.id.desc()).first())
    assert log is not None and "OCR อ่านผิด" in log.detail


def test_edit_receipt_amount_driver_forbidden(client, staff):
    db = staff
    sv = login(client, "SV01")
    rid = _make_receipt(client, db, sv)
    h = login(client, "D01")
    assert client.patch(f"/receipts/{rid}/amount",
                        json={"new_amount": 1, "reason": "x"}, headers=h).status_code == 403


# =========================== task 3: Deduction Leaderboard ===========================
def test_deduction_leaderboard(client, staff):
    db = staff
    # เพิ่มคนขับที่ 2
    d2 = User(emp_id="D02", name="สมหญิง ขยัน", phone="0810000002",
              role=Role.DRIVER, active=True, password_hash=hash_password("1234"))
    db.add(d2)
    db.commit()
    db.refresh(d2)
    d01 = db.query(User).filter(User.emp_id == "D01").first()
    now = datetime.now(timezone.utc)
    # D01 โดนหัก 2 ครั้ง รวม 300 · D02 โดนหัก 1 ครั้ง 500
    db.add_all([
        Penalty(trip_id=1, driver_id=d01.id, amount=100, reason="a", created_by=d01.id, created_at=now),
        Penalty(trip_id=1, driver_id=d01.id, amount=200, reason="b", created_by=d01.id, created_at=now),
        Penalty(trip_id=1, driver_id=d2.id, amount=500, reason="c", created_by=d2.id, created_at=now),
    ])
    db.commit()

    sv = login(client, "SV01")
    rows = client.get(f"/penalties/leaderboard?month={now.month}&year={now.year}", headers=sv).json()
    assert len(rows) == 2
    # เรียงจากมาก→น้อย: D02 (500) มาก่อน D01 (300)
    assert rows[0]["driver_name"] == "สมหญิง ขยัน" and rows[0]["total_amount"] == 500 and rows[0]["count"] == 1
    assert rows[1]["total_amount"] == 300 and rows[1]["count"] == 2
    # คนละปี → ว่าง
    assert client.get(f"/penalties/leaderboard?year={now.year - 1}", headers=sv).json() == []


def test_leaderboard_driver_forbidden(client, staff):
    assert client.get("/penalties/leaderboard", headers=login(client, "D01")).status_code == 403


# =========================== task 5: Audit Log read ===========================
def test_audit_log_rbac(client, staff):
    # Driver + Supervisor เข้าไม่ได้ (Admin+ เท่านั้น)
    assert client.get("/audit-logs", headers=login(client, "D01")).status_code == 403
    assert client.get("/audit-logs", headers=login(client, "SV01")).status_code == 403
    assert client.get("/audit-logs", headers=login(client, "AD01")).status_code == 200


def test_audit_log_records_events(client, staff):
    db = staff
    trip = _trip(db, "T-AL1", status=TripStatus.ORANGE)
    sv = login(client, "SV01")
    client.post(f"/trips/{trip.id}/override-status",
                json={"status": "GREEN", "reason": "ทดสอบ audit"}, headers=sv)
    ad = login(client, "AD01")
    rows = client.get("/audit-logs?action=เปลี่ยนสถานะ", headers=ad).json()
    assert len(rows) >= 1
    assert all("เปลี่ยนสถานะ" in r["action"] for r in rows)
    assert "ทดสอบ audit" in rows[0]["detail"]
