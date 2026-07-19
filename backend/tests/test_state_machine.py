"""Unit tests: State Machine 3 สี + GPS Geofencing

จำลองครบทุกเส้นทางการเปลี่ยนสี และการยิงพิกัด GPS ทั้งต้นทาง/ปลายทาง
รวมถึงการ์ด soft-block / warn-don't-block และ idempotency (กันกดซ้ำ)
"""
import pytest

from app.models import Drop, GpsLog, Trip, User
from app.models.enums import GpsEvent, Role, TripStatus
from tests.conftest import ODO_PHOTO, pass_inspection
from app.services.state_machine import (
    TransitionError,
    TransitionWarning,
    assign_trip,
    close_trip,
    complete_trip,
    finish_loading,
    record_delivery,
)


# --------------------------- helpers / fixtures ---------------------------
def _mk_trip(db, driver, status=TripStatus.WHITE, n_drops=2):
    trip = Trip(code="T-001", driver_id=driver.id, status=status, distance_km=100)
    db.add(trip)
    db.commit()
    db.refresh(trip)
    for i in range(1, n_drops + 1):
        db.add(Drop(trip_id=trip.id, seq=i, name=f"จุด {i}", allowance=300))
    db.commit()
    db.refresh(trip)
    return trip


@pytest.fixture()
def driver(db_session):
    return db_session.query(User).filter(User.emp_id == "D01").first()


@pytest.fixture()
def supervisor(db_session):
    sv = User(emp_id="SV01", name="ธนพล คุมงาน", phone="0820000001",
              role=Role.SUPERVISOR, active=True)
    db_session.add(sv)
    db_session.commit()
    db_session.refresh(sv)
    return sv


def _count_gps(db, event=None):
    q = db.query(GpsLog)
    if event:
        q = q.filter(GpsLog.event == event)
    return q.count()


# ------------------------------ happy path -------------------------------
def test_full_lifecycle_white_orange_green_white(db_session, driver, supervisor):
    """เส้นทางสมบูรณ์: WHITE → ORANGE → GREEN → ส่งงานย่อยครบ (คนขับกลับ WHITE)
    → Supervisor กด "จบเที่ยว" → ล็อกการเงิน"""
    trip = _mk_trip(db_session, driver, n_drops=2)
    assert trip.status is TripStatus.WHITE

    # จ่ายงาน → ORANGE + ผูกทะเบียน
    assign_trip(db_session, trip, "1กก-1234", supervisor)
    assert trip.status is TripStatus.ORANGE
    assert trip.plate == "1กก-1234"
    assert trip.assigned_at is not None

    # ขนของขึ้นเสร็จ → GREEN + GPS ต้นทาง
    pass_inspection(db_session, trip, driver)
    finish_loading(db_session, trip, driver, 13.7563, 100.5018, odometer_start=1000, odometer_photo_b64=ODO_PHOTO)
    assert trip.status is TripStatus.GREEN
    assert trip.finished_loading_at is not None
    assert _count_gps(db_session, GpsEvent.LOADED) == 1

    # ส่งงานย่อยใบแรก → คนขับกลับเป็น "รองาน" (WHITE) ทันที แต่เที่ยวหลักยัง Active
    record_delivery(db_session, trip.drops[0], driver, 13.81, 100.6)
    assert trip.status is TripStatus.WHITE
    assert trip.completed_at is None

    # ขาถัดไปวิ่งเองไม่ได้ — ต้องให้คนคุมงานจ่ายงานย่อยใหม่ก่อน
    with pytest.raises(TransitionError):
        record_delivery(db_session, trip.drops[1], driver, 13.82, 100.6)
    assign_trip(db_session, trip, "1กก-1234", supervisor)
    finish_loading(db_session, trip, driver, 13.75, 100.5)

    # ส่งงานย่อยใบสุดท้าย → ยังไม่จบเที่ยวเอง ต้องรอ Supervisor กด
    record_delivery(db_session, trip.drops[1], driver, 13.82, 100.6)
    assert all(d.delivered and d.photo for d in trip.drops)
    assert trip.status is TripStatus.WHITE
    assert trip.completed_at is None
    assert trip.closed_at is None
    assert _count_gps(db_session, GpsEvent.DELIVERED) == 2

    # Supervisor กด "จบเที่ยว" → เที่ยวหลักจบสมบูรณ์ (ยังไม่ freeze)
    complete_trip(db_session, trip, supervisor)
    assert trip.completed_at is not None
    assert trip.frozen is False

    # คนคุมงานล็อกการเงิน (freeze) หลังตรวจบิลเสร็จ
    close_trip(db_session, trip, supervisor)
    assert trip.status is TripStatus.WHITE
    assert trip.frozen is True


# ------------------------------ assign guards ----------------------------
def test_assign_requires_plate(db_session, driver, supervisor):
    trip = _mk_trip(db_session, driver)
    with pytest.raises(TransitionError):
        assign_trip(db_session, trip, "", supervisor)
    assert trip.status is TripStatus.WHITE


def test_assign_out_of_sequence_warns_then_force(db_session, driver, supervisor):
    """จ่ายงานทับทริปที่กำลังวิ่ง (GREEN) → เตือนก่อน, force แล้วผ่าน + ตั้ง override"""
    trip = _mk_trip(db_session, driver, status=TripStatus.GREEN)
    with pytest.raises(TransitionWarning):
        assign_trip(db_session, trip, "1กก-1234", supervisor)

    assign_trip(db_session, trip, "1กก-1234", supervisor, force=True)
    assert trip.status is TripStatus.ORANGE
    assert trip.override is True


# --------------------------- finish_loading guards -----------------------
def test_finish_loading_soft_block_tarpaulin(db_session, driver, supervisor):
    """Soft-block: ไปสีเขียวได้แม้ยังไม่มีรูปผ้าใบ (ห้าม hard-block)"""
    trip = _mk_trip(db_session, driver)
    assign_trip(db_session, trip, "1กก-1234", supervisor)
    assert all(not d.tarp for d in trip.drops)  # ยังไม่มีรูปผ้าใบเลย

    pass_inspection(db_session, trip, driver)
    finish_loading(db_session, trip, driver, 13.75, 100.5, odometer_start=1000, odometer_photo_b64=ODO_PHOTO)  # ต้องไม่ throw
    assert trip.status is TripStatus.GREEN


def test_finish_loading_out_of_sequence_warns(db_session, driver):
    """กดขนของเสร็จทั้งที่ยังไม่ถูกจ่ายงาน (WHITE) → เตือน; force แล้ว override"""
    trip = _mk_trip(db_session, driver)  # ยังเป็น WHITE
    with pytest.raises(TransitionWarning):
        finish_loading(db_session, trip, driver, 13.75, 100.5, odometer_start=1000, odometer_photo_b64=ODO_PHOTO)

    finish_loading(db_session, trip, driver, 13.75, 100.5, force=True, odometer_start=1000, odometer_photo_b64=ODO_PHOTO)
    assert trip.status is TripStatus.GREEN
    assert trip.override is True
    assert _count_gps(db_session, GpsEvent.LOADED) == 1


def test_finish_loading_idempotent_double_tap(db_session, driver, supervisor):
    """กด 'ขนของขึ้นเสร็จ' ซ้ำ (double-tap) → ไม่สร้าง GPS log ต้นทางซ้ำ"""
    trip = _mk_trip(db_session, driver)
    assign_trip(db_session, trip, "1กก-1234", supervisor)

    pass_inspection(db_session, trip, driver)
    finish_loading(db_session, trip, driver, 13.75, 100.5, odometer_start=1000, odometer_photo_b64=ODO_PHOTO)
    finish_loading(db_session, trip, driver, 13.75, 100.5, odometer_start=1000, odometer_photo_b64=ODO_PHOTO)  # กดซ้ำ
    assert _count_gps(db_session, GpsEvent.LOADED) == 1


# ---------------------------- record_delivery ----------------------------
def test_record_delivery_requires_green(db_session, driver, supervisor):
    """ส่งของไม่ได้ถ้าทริปยังไม่ GREEN (hard-block)"""
    trip = _mk_trip(db_session, driver)
    assign_trip(db_session, trip, "1กก-1234", supervisor)  # ORANGE
    with pytest.raises(TransitionError):
        record_delivery(db_session, trip.drops[0], driver, 13.8, 100.6)


def test_record_delivery_idempotent(db_session, driver, supervisor):
    trip = _mk_trip(db_session, driver)
    assign_trip(db_session, trip, "1กก-1234", supervisor)
    pass_inspection(db_session, trip, driver)
    finish_loading(db_session, trip, driver, 13.75, 100.5, odometer_start=1000, odometer_photo_b64=ODO_PHOTO)

    d = trip.drops[0]
    record_delivery(db_session, d, driver, 13.8, 100.6)
    record_delivery(db_session, d, driver, 13.8, 100.6)  # ซ้ำ
    assert _count_gps(db_session, GpsEvent.DELIVERED) == 1


# ------------------------------- close_trip ------------------------------
def test_close_requires_completed_trip(db_session, driver, supervisor):
    """ยังไม่กด "จบเที่ยว" → ล็อกการเงินไม่ได้"""
    trip = _mk_trip(db_session, driver)  # WHITE · เที่ยวหลักยัง Active
    with pytest.raises(TransitionError):
        close_trip(db_session, trip, supervisor)


def test_complete_trip_blocks_second_time_and_when_frozen(db_session, driver, supervisor):
    trip = _mk_trip(db_session, driver, n_drops=1)
    complete_trip(db_session, trip, supervisor, force=True)
    with pytest.raises(TransitionError):
        complete_trip(db_session, trip, supervisor, force=True)


def test_close_warns_when_photos_incomplete(db_session, driver, supervisor):
    """ปิดงานทั้งที่รูปส่งไม่ครบ → เตือน; force แล้วปิดได้ + override"""
    trip = _mk_trip(db_session, driver, n_drops=2)
    assign_trip(db_session, trip, "1กก-1234", supervisor)
    pass_inspection(db_session, trip, driver)
    finish_loading(db_session, trip, driver, 13.75, 100.5, odometer_start=1000, odometer_photo_b64=ODO_PHOTO)
    record_delivery(db_session, trip.drops[0], driver, 13.8, 100.6)  # ส่งแค่จุดเดียว

    # ยังส่งไม่ครบ → จบเที่ยวต้องยืนยันก่อน
    with pytest.raises(TransitionWarning):
        complete_trip(db_session, trip, supervisor)
    complete_trip(db_session, trip, supervisor, force=True)

    with pytest.raises(TransitionWarning):
        close_trip(db_session, trip, supervisor)

    close_trip(db_session, trip, supervisor, force=True)
    assert trip.status is TripStatus.WHITE
    assert trip.frozen is True
    assert trip.override is True
