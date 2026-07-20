"""Tests: ยืนยันขนของขึ้นเสร็จ (รูปของบนรถ) + อัปบิลระหว่างทางได้ตลอด (🟠/🟢)

Phase 1: finish_loading บังคับ loaded_photo_b64 → เก็บลง Drop.loaded_photo ของขาปัจจุบัน
Phase 2: /trips/{id}/receipt อัปได้ทั้งตอน ORANGE และ GREEN · อัปกี่ใบก็ได้
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Drop, Receipt, Trip, User
from app.models.enums import ReceiptKind, Role, TripStatus
from app.security import hash_password
from app.services.evidence import EvidenceError, log_trip_receipt
from app.services.finance import total_liters
from app.services.state_machine import (
    TransitionError,
    add_drop,
    assign_trip,
    current_leg,
    finish_loading,
    record_delivery,
)
from tests.conftest import PHOTO, ODO_PHOTO, pass_inspection


def login(client, ident, pw="1234"):
    r = client.post("/auth/login", json={"identifier": ident, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def driver(db_session):
    return db_session.query(User).filter(User.emp_id == "D01").first()


@pytest.fixture()
def supervisor(db_session):
    sv = User(emp_id="SV01", name="ธนพล คุมงาน", phone="0820000001",
              role=Role.SUPERVISOR, active=True, password_hash=hash_password("1234"))
    db_session.add(sv)
    db_session.commit()
    return sv


def _orange_trip(db, driver, supervisor, code="T-LD1"):
    """เที่ยวที่จ่ายงานแล้ว + ตรวจรถผ่าน — พร้อมกด "ขนของขึ้นเสร็จ" (ยังเป็น 🟠)"""
    trip = Trip(code=code, driver_id=driver.id, distance_km=0)
    db.add(trip)
    db.commit()
    db.add(Drop(trip_id=trip.id, seq=1, name="ลำปาง → กรุงเทพฯ",
                origin="ลำปาง", destination="กรุงเทพฯ", allowance=500))
    db.commit()
    db.refresh(trip)
    assign_trip(db, trip, "1กก-1234", supervisor)
    pass_inspection(db, trip, driver)
    return trip


# =================== Phase 1: รูปของที่ขนขึ้นรถ ===================
def test_finish_loading_requires_loaded_photo(db_session, driver, supervisor):
    trip = _orange_trip(db_session, driver, supervisor)
    with pytest.raises(TransitionError):
        finish_loading(db_session, trip, driver, 13.75, 100.5)   # ไม่แนบรูปของ
    assert trip.status is TripStatus.ORANGE          # ยังไม่เปลี่ยนเป็นเขียว
    assert trip.drops[0].loaded_photo is None


def test_finish_loading_stores_photo_on_current_leg(db_session, driver, supervisor):
    trip = _orange_trip(db_session, driver, supervisor)
    finish_loading(db_session, trip, driver, 13.75, 100.5, loaded_photo_b64=PHOTO)

    assert trip.status is TripStatus.GREEN
    assert trip.drops[0].loaded_photo.startswith("/uploads/loaded-")


def test_each_leg_gets_its_own_loaded_photo(db_session, driver, supervisor):
    """ขาใหม่ = รูปใหม่ · รูปของขาเก่าไม่ถูกทับ"""
    trip = _orange_trip(db_session, driver, supervisor)
    finish_loading(db_session, trip, driver, 13.75, 100.5, loaded_photo_b64=PHOTO)
    record_delivery(db_session, trip.drops[0], driver, 13.8, 100.6, photo_b64=PHOTO)
    first = trip.drops[0].loaded_photo

    add_drop(db_session, trip, supervisor, origin="กรุงเทพฯ", destination="ชลบุรี", revenue=8000)
    assign_trip(db_session, trip, "1กก-1234", supervisor)
    finish_loading(db_session, trip, driver, 13.75, 100.5, loaded_photo_b64=PHOTO)

    second = trip.drops[1].loaded_photo
    assert second and second.startswith("/uploads/loaded-")
    assert trip.drops[0].loaded_photo == first   # ขาเก่าไม่โดนทับ
    assert second != first


def test_current_leg_picks_latest_unsent_leg(db_session, driver, supervisor):
    """ขาปัจจุบัน = ขาที่ยังไม่ส่ง seq มากสุด (ตรงกับที่คนขับเห็นบนจอ)"""
    trip = _orange_trip(db_session, driver, supervisor)
    finish_loading(db_session, trip, driver, 13.75, 100.5, loaded_photo_b64=PHOTO)
    record_delivery(db_session, trip.drops[0], driver, 13.8, 100.6, photo_b64=PHOTO)
    add_drop(db_session, trip, supervisor, origin="กรุงเทพฯ", destination="ชลบุรี", revenue=8000)

    assert current_leg(trip).seq == 2


def test_finish_loading_api_rejects_missing_loaded_photo(client, db_session, driver, supervisor):
    trip = _orange_trip(db_session, driver, supervisor, code="T-LD2")
    drv = login(client, "D01")
    body = {"lat": 13.7, "lng": 100.5}
    assert client.post(f"/trips/{trip.id}/finish-loading", json=body,
                       headers=drv).status_code == 422

    ok = client.post(f"/trips/{trip.id}/finish-loading",
                     json={**body, "loaded_photo_b64": ODO_PHOTO}, headers=drv)
    assert ok.status_code == 200 and ok.json()["status"] == "GREEN"
    assert ok.json()["drops"][0]["loaded_photo"].startswith("/uploads/loaded-")


# =================== Phase 2: อัปบิลระหว่างทาง ===================
def test_mid_trip_receipt_works_in_orange(client, db_session, driver, supervisor):
    """🟠 ยังไม่ขึ้นของก็อัปบิลได้ — ไม่ต้องรอถึงตอนส่งของ"""
    trip = _orange_trip(db_session, driver, supervisor, code="T-MT1")
    drv = login(client, "D01")
    r = client.post(f"/trips/{trip.id}/receipt",
                    json={"kind": "FUEL", "photo_b64": ODO_PHOTO, "liters": 40}, headers=drv)
    assert r.status_code == 200
    assert r.json()["amount"] == 0                      # ไม่มี OCR
    assert r.json()["photo"].startswith("/uploads/fuel-")


def test_mid_trip_receipt_multiple_times(db_session, driver, supervisor):
    """แวะปั๊มหลายรอบ = อัปได้หลายใบ ไม่ชน UniqueConstraint แบบบิลรายจุด"""
    trip = _orange_trip(db_session, driver, supervisor, code="T-MT2")
    finish_loading(db_session, trip, driver, 13.75, 100.5, loaded_photo_b64=PHOTO)

    log_trip_receipt(db_session, trip, driver, ReceiptKind.FUEL, photo_b64=PHOTO, liters=30)
    log_trip_receipt(db_session, trip, driver, ReceiptKind.FUEL, photo_b64=PHOTO, liters=25.5)
    log_trip_receipt(db_session, trip, driver, ReceiptKind.TOLL, photo_b64=PHOTO)
    db_session.refresh(trip)

    rows = db_session.query(Receipt).filter(Receipt.trip_id == trip.id).all()
    assert len(rows) == 3
    assert total_liters(trip) == 55.5      # ลิตรทุกใบถูกรวมไปคิด km/L
    assert all(r.drop_id is None and not r.approved for r in rows)


def test_mid_trip_fuel_requires_liters(db_session, driver, supervisor):
    trip = _orange_trip(db_session, driver, supervisor, code="T-MT3")
    with pytest.raises(EvidenceError):
        log_trip_receipt(db_session, trip, driver, ReceiptKind.FUEL, photo_b64=PHOTO)
    # บิลทางหลวงไม่ต้องมีลิตร
    toll = log_trip_receipt(db_session, trip, driver, ReceiptKind.TOLL, photo_b64=PHOTO)
    assert toll.liters == 0


def test_mid_trip_receipt_requires_photo(db_session, driver, supervisor):
    trip = _orange_trip(db_session, driver, supervisor, code="T-MT4")
    with pytest.raises(EvidenceError):
        log_trip_receipt(db_session, trip, driver, ReceiptKind.TOLL)


def test_mid_trip_receipt_blocked_when_not_running(client, db_session, driver, supervisor):
    """ทริปที่ยังไม่ถูกจ่ายงาน (⚪) อัปบิลระหว่างทางไม่ได้"""
    trip = Trip(code="T-MT5", driver_id=driver.id, status=TripStatus.WHITE)
    db_session.add(trip)
    db_session.commit()
    db_session.add(Drop(trip_id=trip.id, seq=1, name="a", origin="ลำปาง",
                        destination="กรุงเทพฯ", allowance=100))
    db_session.commit()

    drv = login(client, "D01")
    r = client.post(f"/trips/{trip.id}/receipt",
                    json={"kind": "TOLL", "photo_b64": ODO_PHOTO}, headers=drv)
    assert r.status_code == 400


def test_mid_trip_receipt_driver_cannot_touch_others_trip(client, db_session, driver, supervisor):
    other = User(emp_id="D02", name="อื่น", phone="0810000099", role=Role.DRIVER,
                 active=True, password_hash=hash_password("1234"))
    db_session.add(other)
    db_session.commit()
    trip = _orange_trip(db_session, driver, supervisor, code="T-MT6")

    r = client.post(f"/trips/{trip.id}/receipt",
                    json={"kind": "TOLL", "photo_b64": ODO_PHOTO}, headers=login(client, "D02"))
    assert r.status_code == 403
