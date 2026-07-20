"""Unit tests: Offline Auto-Sync ฝั่ง backend (ข้อ 1.1)

ข้อมูลที่ sync ทีหลังต้องคงเวลา "ตอนกดจริง" (captured_at) ไม่ใช่เวลาที่เน็ตกลับมา
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.models import Drop, GpsLog, Trip, User
from app.models.enums import GpsEvent, IncidentKind, Role
from app.services.evidence import upload_receipt
from app.services.incident import report_sos
from app.services.state_machine import assign_trip, finish_loading, record_delivery
from app.models.enums import ReceiptKind
from tests.conftest import PHOTO, ODO_PHOTO, pass_inspection


@pytest.fixture()
def driver(db_session):
    return db_session.query(User).filter(User.emp_id == "D01").first()


@pytest.fixture()
def supervisor(db_session):
    sv = User(emp_id="SV01", name="ธนพล คุมงาน", phone="0820000001",
              role=Role.SUPERVISOR, active=True)
    db_session.add(sv)
    db_session.commit()
    return sv


PRESSED = datetime.now(timezone.utc) - timedelta(hours=2)  # กดปุ่มไว้เมื่อ 2 ชม.ก่อน (ออฟไลน์)


def _naive(dt):
    """SQLite คืน naive datetime — เทียบแบบตัด tzinfo"""
    return dt.replace(tzinfo=None)


def _orange_trip(db, driver, supervisor):
    trip = Trip(code="T-400", driver_id=driver.id)
    db.add(trip)
    db.commit()
    db.add(Drop(origin="ต้นทาง", destination="ปลายทาง", trip_id=trip.id, seq=1, name="จุด 1", allowance=300))
    db.commit()
    db.refresh(trip)
    assign_trip(db, trip, "1กก-1234", supervisor)
    pass_inspection(db, trip, driver)
    return trip


def test_finish_loading_keeps_captured_at(db_session, driver, supervisor):
    trip = _orange_trip(db_session, driver, supervisor)
    finish_loading(db_session, trip, driver, 13.75, 100.5, captured_at=PRESSED, odometer_start=1000, odometer_photo_b64=ODO_PHOTO, loaded_photo_b64=PHOTO)

    assert _naive(trip.finished_loading_at) == _naive(PRESSED)
    log = db_session.query(GpsLog).filter_by(trip_id=trip.id, event=GpsEvent.LOADED).one()
    assert _naive(log.recorded_at) == _naive(PRESSED)


def test_delivery_keeps_captured_at(db_session, driver, supervisor):
    trip = _orange_trip(db_session, driver, supervisor)
    finish_loading(db_session, trip, driver, 13.75, 100.5, odometer_start=1000, odometer_photo_b64=ODO_PHOTO, loaded_photo_b64=PHOTO)
    drop = trip.drops[0]
    record_delivery(db_session, drop, driver, 13.8, 100.6, captured_at=PRESSED, photo_b64=PHOTO)

    assert _naive(drop.delivered_at) == _naive(PRESSED)
    log = db_session.query(GpsLog).filter_by(drop_id=drop.id, event=GpsEvent.DELIVERED).one()
    assert _naive(log.recorded_at) == _naive(PRESSED)


def test_receipt_keeps_captured_at(db_session, driver, supervisor):
    trip = _orange_trip(db_session, driver, supervisor)
    finish_loading(db_session, trip, driver, 13.75, 100.5, odometer_start=1000, odometer_photo_b64=ODO_PHOTO, loaded_photo_b64=PHOTO)
    r = upload_receipt(db_session, trip.drops[0], driver, ReceiptKind.FUEL, captured_at=PRESSED, photo_b64=PHOTO)
    assert _naive(r.created_at) == _naive(PRESSED)


def test_sos_keeps_captured_at(db_session, driver, supervisor):
    trip = _orange_trip(db_session, driver, supervisor)
    inc = report_sos(db_session, trip, driver, IncidentKind.BREAKDOWN, captured_at=PRESSED)
    assert _naive(inc.created_at) == _naive(PRESSED)


def test_without_captured_at_uses_now(db_session, driver, supervisor):
    trip = _orange_trip(db_session, driver, supervisor)
    before = datetime.now(timezone.utc) - timedelta(seconds=5)
    finish_loading(db_session, trip, driver, 13.75, 100.5, odometer_start=1000, odometer_photo_b64=ODO_PHOTO, loaded_photo_b64=PHOTO)
    assert _naive(trip.finished_loading_at) >= _naive(before)
