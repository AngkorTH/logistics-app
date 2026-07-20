"""Integration tests: 3 เฟสอัปเดต (รูปหน้าปัดตอนจบงาน · ประวัติคนขับ · แจ้งเตือนหักเงิน ·
NOT NULL ต้นทาง/ปลายทาง · หลักฐานเป็นไฟล์จริง · ปิด OCR · แอดมินสั่งรถเข้าซ่อม)
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.main import app
from app.models import Drop, Notification, Trip, User, Vehicle
from app.models.enums import ReceiptKind, Role, TripStatus, VehicleStatus
from app.security import hash_password
from app.services.evidence import EvidenceError, upload_receipt
from app.services.finance import apply_penalty
from app.services.penalty import add_penalty
from app.services.state_machine import TransitionError, end_trip
from tests.conftest import PHOTO


def login(client, ident, pw="1234"):
    r = client.post("/auth/login", json={"identifier": ident, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def staff(db_session):
    db_session.add(User(emp_id="SV01", name="ธนพล คุมงาน", phone="0820000001",
                        role=Role.SUPERVISOR, active=True, password_hash=hash_password("1234")))
    db_session.commit()
    return db_session


@pytest.fixture()
def driver(db_session):
    return db_session.query(User).filter(User.emp_id == "D01").first()


def _trip(db, driver, code="T-P1", odometer_start=1000):
    trip = Trip(code=code, driver_id=driver.id, status=TripStatus.GREEN,
                odometer_start=odometer_start)
    db.add(trip)
    db.commit()
    db.add(Drop(trip_id=trip.id, seq=1, name="ขา 1", origin="ลำปาง", destination="กรุงเทพฯ",
                allowance=300, delivered=True))
    db.commit()
    db.refresh(trip)
    return trip


# ---------- Phase 1.1: รูปหน้าปัดไมล์ตอนจบงาน (บังคับ) ----------
def test_end_trip_requires_odometer_photo(db_session, driver):
    trip = _trip(db_session, driver)
    with pytest.raises(TransitionError):
        end_trip(db_session, trip, driver, 1250)          # ไม่แนบรูป → บล็อก
    assert trip.odometer_end is None


def test_end_trip_stores_real_photo_path(db_session, driver):
    trip = _trip(db_session, driver)
    end_trip(db_session, trip, driver, 1250, odometer_photo_b64=PHOTO)
    assert trip.odometer_end == 1250
    assert trip.odometer_end_photo.startswith("/uploads/odo-end-")


def test_end_trip_api_rejects_missing_photo(client, db_session, driver):
    trip = _trip(db_session, driver, code="T-P2")
    h = login(client, "D01")
    assert client.post(f"/trips/{trip.id}/end",
                       json={"odometer_end": 1250}, headers=h).status_code == 422
    r = client.post(f"/trips/{trip.id}/end",
                    json={"odometer_end": 1250, "odometer_photo_b64": PHOTO}, headers=h)
    assert r.status_code == 200
    assert r.json()["odometer_end_photo"].startswith("/uploads/odo-end-")


# ---------- Phase 1.2: คนขับดูประวัติของตัวเองได้ ----------
def test_driver_reads_own_history_only(client, staff, driver):
    other = staff.query(User).filter(User.emp_id == "D04").first()
    h = login(client, "D01")
    assert client.get(f"/users/{driver.id}/history/monthly", headers=h).status_code == 200
    assert client.get(f"/users/{other.id}/history/monthly", headers=h).status_code == 403
    # Supervisor ยังดูของคนขับได้เหมือนเดิม
    assert client.get(f"/users/{driver.id}/history/monthly",
                      headers=login(client, "SV01")).status_code == 200


# ---------- Phase 1.3: หักเงินแล้วต้องมีแจ้งเตือนจริงใน DB ----------
def test_penalty_creates_real_notification(db_session, driver):
    sv = User(emp_id="SV09", name="คุมงาน", phone="0829999999", role=Role.SUPERVISOR, active=True)
    db_session.add(sv)
    db_session.commit()
    trip = _trip(db_session, driver, code="T-P3")

    add_penalty(db_session, trip, sv, 100, "ส่งช้า")
    rows = db_session.query(Notification).filter(Notification.kind == "PENALTY_APPLIED").all()
    assert len(rows) == 1
    assert "ส่งช้า" in rows[0].message and rows[0].trip_id == trip.id

    # ยอดหักแบบก้อนเดียว (apply_penalty) ก็ต้องแจ้งเตือนเช่นกัน
    apply_penalty(db_session, trip, sv, 50, "ผ้าใบไม่คลุม")
    assert db_session.query(Notification).filter(
        Notification.kind == "PENALTY_APPLIED").count() == 2


# ---------- Phase 1.4: ต้นทาง/ปลายทาง ห้ามว่างระดับ DB ----------
def test_drop_origin_destination_not_null(db_session, driver):
    trip = _trip(db_session, driver, code="T-P4")
    db_session.add(Drop(trip_id=trip.id, seq=2, name="ไม่มีต้นทาง", allowance=100))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_drop_origin_cannot_be_blank_string(db_session, driver):
    trip = _trip(db_session, driver, code="T-P5")
    db_session.add(Drop(trip_id=trip.id, seq=2, name="ว่าง", origin="  ",
                        destination="กรุงเทพฯ", allowance=100))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_create_trip_api_rejects_blank_origin(client, staff, driver):
    sv = login(client, "SV01")
    body = {"driver_id": driver.id, "drops": [
        {"origin": "   ", "destination": "กรุงเทพฯ", "revenue": 1000}]}
    assert client.post("/trips", json=body, headers=sv).status_code == 422


# ---------- Phase 2: หลักฐานเก็บ path จริง + ปิด OCR ----------
def test_receipt_upload_requires_photo_and_has_no_ocr(client, staff, driver):
    trip = _trip(db := staff, driver, code="T-P6")
    drop = trip.drops[0]
    h = login(client, "D01")

    # ไม่มีรูป → 422 (schema บังคับ)
    assert client.post(f"/drops/{drop.id}/receipt",
                       json={"kind": "FUEL"}, headers=h).status_code == 422

    r = client.post(f"/drops/{drop.id}/receipt",
                    json={"kind": "FUEL", "photo_b64": PHOTO}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["amount"] == 0 and body["date"] is None      # ไม่มี OCR
    assert body["photo"].startswith("/uploads/rcpt-")        # path ไฟล์จริง

    # Supervisor ต้องคีย์ทั้งยอดและวันที่ — ขาดอย่างใดอย่างหนึ่ง = 422
    sv = login(client, "SV01")
    rid = body["id"]
    assert client.post(f"/receipts/{rid}/approve",
                       json={"amount": 500}, headers=sv).status_code == 422
    ok = client.post(f"/receipts/{rid}/approve",
                     json={"amount": 500, "date": "2026-07-19"}, headers=sv)
    assert ok.status_code == 200
    assert ok.json()["amount"] == 500 and ok.json()["date"] == "2026-07-19"
    assert ok.json()["approved"] is True


def test_no_attached_marker_anywhere(db_session, driver):
    """หลักฐานที่ไม่มีรูป = บันทึกไม่ได้ (ไม่มี fallback "attached" อีกแล้ว)"""
    trip = _trip(db_session, driver, code="T-P7")
    with pytest.raises(EvidenceError):
        upload_receipt(db_session, trip.drops[0], driver, ReceiptKind.FUEL)


# ---------- Phase 3: แอดมินสั่งรถเข้าซ่อม (Supervisor ทำไม่ได้) ----------
def test_only_admin_can_set_vehicle_repair(client, staff, driver):
    db = staff
    v = Vehicle(plate="1กก-1234", model="Isuzu", driver_id=driver.id)
    db.add(v)
    db.commit()
    db.refresh(v)

    body = {"status": "MAINTENANCE", "reason": "เข้าศูนย์เปลี่ยนยาง"}
    # Driver / Supervisor → 403
    assert client.post(f"/vehicles/{v.id}/status", json=body,
                       headers=login(client, "D01")).status_code == 403
    assert client.post(f"/vehicles/{v.id}/status", json=body,
                       headers=login(client, "SV01")).status_code == 403

    ad = login(client, "AD01")
    # ต้องมีเหตุผลเสมอ
    assert client.post(f"/vehicles/{v.id}/status",
                       json={"status": "MAINTENANCE", "reason": ""}, headers=ad).status_code == 422

    r = client.post(f"/vehicles/{v.id}/status", json=body, headers=ad)
    assert r.status_code == 200 and r.json()["status"] == "MAINTENANCE"

    # รถกำลังซ่อม → จ่ายงานไม่ได้
    trip = _trip(db, driver, code="T-P8")
    trip.status = TripStatus.WHITE
    db.commit()
    assert client.post(f"/trips/{trip.id}/assign", json={},
                       headers=login(client, "SV01")).status_code == 400

    # ปลดล็อกกลับมาใช้งานได้
    back = client.post(f"/vehicles/{v.id}/status",
                       json={"status": "AVAILABLE", "reason": "ซ่อมเสร็จ"}, headers=ad)
    assert back.status_code == 200 and back.json()["status"] == VehicleStatus.AVAILABLE.value
