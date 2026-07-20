"""Unit tests: Pre-trip Inspection (ข้อ 1.2)

- ติ๊กผ่านทุกข้อ → PASSED → กดขนของขึ้นเสร็จได้
- มีจุดชำรุด: ไม่มีรูป → error / มีรูป → PENDING_REVIEW + แจ้งเตือน + ล็อกปุ่ม
- Supervisor APPROVED → ปลดล็อก / REJECTED → ยังล็อก
"""
import pytest

from tests.conftest import PHOTO, ODO_PHOTO

from app.models import Drop, Notification, Role, Trip, User
from app.models.enums import InspectionStatus, TripStatus
from app.services.inspection import (
    InspectionError,
    review_inspection,
    submit_inspection,
)
from app.services.state_machine import TransitionError, assign_trip, finish_loading


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


@pytest.fixture()
def orange_trip(db_session, driver, supervisor):
    trip = Trip(code="T-100", driver_id=driver.id)
    db_session.add(trip)
    db_session.commit()
    db_session.add(Drop(origin="ต้นทาง", destination="ปลายทาง", trip_id=trip.id, seq=1, name="จุด 1", allowance=300))
    db_session.commit()
    assign_trip(db_session, trip, "1กก-1234", supervisor)
    return trip


def test_all_pass_unlocks_finish_loading(db_session, orange_trip, driver, loaded_photo_b64=PHOTO):
    ins = submit_inspection(db_session, orange_trip, driver, {"tires": True, "lights": True}, odometer_start=1000, odometer_photo_b64=ODO_PHOTO)
    assert ins.status is InspectionStatus.PASSED

    finish_loading(db_session, orange_trip, driver, 13.75, 100.5, odometer_start=1000, odometer_photo_b64=ODO_PHOTO, loaded_photo_b64=PHOTO)
    assert orange_trip.status is TripStatus.GREEN


def test_finish_loading_blocked_without_inspection(db_session, orange_trip, driver):
    with pytest.raises(TransitionError):
        finish_loading(db_session, orange_trip, driver, 13.75, 100.5, odometer_start=1000, odometer_photo_b64=ODO_PHOTO, loaded_photo_b64=PHOTO)
    # force ก็ข้ามด่านตรวจรถไม่ได้ (hard-block)
    with pytest.raises(TransitionError):
        finish_loading(db_session, orange_trip, driver, 13.75, 100.5, force=True, odometer_start=1000, odometer_photo_b64=ODO_PHOTO, loaded_photo_b64=PHOTO)


def test_defect_requires_photo(db_session, orange_trip, driver):
    with pytest.raises(InspectionError):
        submit_inspection(db_session, orange_trip, driver, {"tires": False}, odometer_start=1000, odometer_photo_b64=ODO_PHOTO)


def test_defect_goes_pending_and_blocks(db_session, orange_trip, driver):
    ins = submit_inspection(
        db_session, orange_trip, driver, {"tires": False, "lights": True},
        defect_note="ยางหน้าซ้ายแตกลาย", defect_photo_b64="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=",
        odometer_start=1000, odometer_photo_b64=ODO_PHOTO,
    )
    assert ins.status is InspectionStatus.PENDING_REVIEW
    # แจ้งเตือนทีมคุมงานถูกสร้าง
    assert db_session.query(Notification).filter_by(kind="INSPECTION_DEFECT").count() == 1
    # ปุ่มขนของขึ้นเสร็จถูกล็อก
    with pytest.raises(TransitionError):
        finish_loading(db_session, orange_trip, driver, 13.75, 100.5, odometer_start=1000, odometer_photo_b64=ODO_PHOTO, loaded_photo_b64=PHOTO)


def test_approve_unlocks_reject_keeps_locked(db_session, orange_trip, driver, supervisor):
    ins = submit_inspection(
        db_session, orange_trip, driver, {"tires": False}, defect_photo_b64="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=",
        odometer_start=1000, odometer_photo_b64=ODO_PHOTO,
    )
    review_inspection(db_session, ins, supervisor, approve=False, note="ห้ามวิ่ง")
    assert ins.status is InspectionStatus.REJECTED
    with pytest.raises(TransitionError):
        finish_loading(db_session, orange_trip, driver, 13.75, 100.5, odometer_start=1000, odometer_photo_b64=ODO_PHOTO, loaded_photo_b64=PHOTO)

    # ตรวจซ้ำใหม่ + supervisor อนุมัติ → ปลดล็อก
    ins2 = submit_inspection(
        db_session, orange_trip, driver, {"tires": False}, defect_photo_b64="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=",
        odometer_start=1000, odometer_photo_b64=ODO_PHOTO,
    )
    review_inspection(db_session, ins2, supervisor, approve=True)
    assert ins2.status is InspectionStatus.APPROVED
    finish_loading(db_session, orange_trip, driver, 13.75, 100.5, odometer_start=1000, odometer_photo_b64=ODO_PHOTO, loaded_photo_b64=PHOTO)
    assert orange_trip.status is TripStatus.GREEN


def test_review_twice_rejected(db_session, orange_trip, driver, supervisor):
    ins = submit_inspection(db_session, orange_trip, driver, {"tires": False}, defect_photo_b64="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=", odometer_start=1000, odometer_photo_b64=ODO_PHOTO)
    review_inspection(db_session, ins, supervisor, approve=True)
    with pytest.raises(InspectionError):
        review_inspection(db_session, ins, supervisor, approve=False)


def test_submit_requires_orange(db_session, driver):
    trip = Trip(code="T-101", driver_id=driver.id)  # WHITE
    db_session.add(trip)
    db_session.commit()
    with pytest.raises(InspectionError):
        submit_inspection(db_session, trip, driver, {"tires": True}, odometer_start=1000, odometer_photo_b64=ODO_PHOTO)
