"""Unit tests: Freeze on Close + Correction Workflow (ล็อก/ปลดล็อกการเงิน)

ครอบคลุม: freeze ตอนปิดงาน + snapshot ยอดน้ำมัน/ทางหลวง,
ขอปลดล็อกบังคับเหตุผล, เฉพาะ Super Admin อนุมัติ, อนุมัติ→เขียนค่าใหม่, ปฏิเสธ→คงเดิม
"""
import pytest

from app.models import Drop, Trip, User
from app.models.enums import CorrectionStatus, ReceiptKind, Role, TripStatus
from app.services.correction import (
    CorrectionError,
    approve_correction,
    reject_correction,
    request_correction,
)
from app.services.evidence import approve_receipt, upload_receipt
from tests.conftest import ODO_PHOTO, pass_inspection
from app.services.state_machine import (
    assign_trip,
    close_trip,
    complete_trip,
    finish_loading,
    record_delivery,
)


def _mk_trip(db, driver, n_drops=2):
    trip = Trip(code="T-040", driver_id=driver.id, status=TripStatus.WHITE, distance_km=100)
    db.add(trip)
    db.commit()
    db.refresh(trip)
    for i in range(1, n_drops + 1):
        db.add(Drop(trip_id=trip.id, seq=i, name=f"จุด {i}", allowance=300))
    db.commit()
    db.refresh(trip)
    return trip


def _run_to_green(db, trip, driver, supervisor):
    assign_trip(db, trip, "1กก-1234", supervisor)
    pass_inspection(db, trip, driver)
    finish_loading(db, trip, driver, 13.75, 100.5, odometer_start=1000, odometer_photo_b64=ODO_PHOTO)


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


@pytest.fixture()
def super_admin(db_session):
    sa = User(emp_id="SA01", name="วิชัย สูงสุด", phone="0840000001",
              role=Role.SUPER_ADMIN, active=True)
    db_session.add(sa)
    db_session.commit()
    db_session.refresh(sa)
    return sa


# ------------------------------- freeze -------------------------------
def test_close_freezes_and_snapshots_amounts(db_session, driver, supervisor):
    """ปิดงาน → frozen=True และ snapshot ยอดน้ำมัน/ทางหลวงจากบิล approved"""
    trip = _mk_trip(db_session, driver, n_drops=2)
    _run_to_green(db_session, trip, driver, supervisor)

    r = upload_receipt(db_session, trip.drops[0], supervisor, ReceiptKind.FUEL, ocr_amount=1200)
    approve_receipt(db_session, r, supervisor)
    t = upload_receipt(db_session, trip.drops[1], supervisor, ReceiptKind.TOLL, ocr_amount=80)
    approve_receipt(db_session, t, supervisor)

    for i, d in enumerate(trip.drops):
        if i > 0:  # ขาถัดไปต้องให้คนคุมงานจ่ายงานย่อยใหม่ก่อน
            assign_trip(db_session, trip, "1กก-1234", supervisor)
            finish_loading(db_session, trip, driver, 13.75, 100.5)
        record_delivery(db_session, d, driver, 13.8, 100.6)
    complete_trip(db_session, trip, supervisor)   # Supervisor กดจบเที่ยวก่อน
    close_trip(db_session, trip, supervisor)

    assert trip.frozen is True
    assert trip.frozen_fuel == 1200
    assert trip.frozen_toll == 80


# --------------------------- request guards ---------------------------
def test_cannot_request_correction_before_freeze(db_session, driver, supervisor):
    trip = _mk_trip(db_session, driver)
    with pytest.raises(CorrectionError):
        request_correction(db_session, trip, supervisor, "fuel", 999, "แก้ก่อน freeze")


def test_request_correction_requires_reason(db_session, driver, supervisor):
    trip = _mk_trip(db_session, driver)
    trip.frozen = True
    trip.frozen_fuel = 1000
    db_session.commit()
    with pytest.raises(CorrectionError):
        request_correction(db_session, trip, supervisor, "fuel", 1100, "")


def test_request_creates_pending_without_touching_value(db_session, driver, supervisor):
    """ขอปลดล็อก → สร้าง PENDING เก็บค่าเก่า/ใหม่ แต่ตัวเลขจริงยังไม่เปลี่ยน"""
    trip = _mk_trip(db_session, driver)
    trip.frozen = True
    trip.frozen_fuel = 1000
    db_session.commit()

    corr = request_correction(db_session, trip, supervisor, "fuel", 1150, "OCR อ่านผิด")
    assert corr.status is CorrectionStatus.PENDING
    assert corr.old_val == 1000 and corr.new_val == 1150
    assert trip.frozen_fuel == 1000  # ยังไม่เปลี่ยน


# --------------------------- approval flow ----------------------------
def test_only_super_admin_can_approve(db_session, driver, supervisor):
    trip = _mk_trip(db_session, driver)
    trip.frozen = True
    trip.frozen_fuel = 1000
    db_session.commit()
    corr = request_correction(db_session, trip, supervisor, "fuel", 1150, "OCR ผิด")

    # supervisor (ไม่ใช่ super admin) อนุมัติไม่ได้
    with pytest.raises(CorrectionError):
        approve_correction(db_session, corr, supervisor)
    assert corr.status is CorrectionStatus.PENDING


def test_approve_writes_new_value(db_session, driver, supervisor, super_admin):
    trip = _mk_trip(db_session, driver)
    trip.frozen = True
    trip.frozen_fuel = 1000
    db_session.commit()
    corr = request_correction(db_session, trip, supervisor, "fuel", 1150, "OCR ผิด")

    approve_correction(db_session, corr, super_admin)
    db_session.refresh(trip)
    assert corr.status is CorrectionStatus.APPROVED
    assert corr.approved_by == super_admin.id
    assert trip.frozen_fuel == 1150  # ค่าใหม่ถูกเขียนจริง


def test_reject_keeps_old_value(db_session, driver, supervisor, super_admin):
    trip = _mk_trip(db_session, driver)
    trip.frozen = True
    trip.frozen_fuel = 1000
    db_session.commit()
    corr = request_correction(db_session, trip, supervisor, "fuel", 1150, "OCR ผิด")

    reject_correction(db_session, corr, super_admin, "หลักฐานไม่พอ")
    db_session.refresh(trip)
    assert corr.status is CorrectionStatus.REJECTED
    assert trip.frozen_fuel == 1000  # คงเดิม


def test_cannot_decide_twice(db_session, driver, supervisor, super_admin):
    trip = _mk_trip(db_session, driver)
    trip.frozen = True
    trip.frozen_fuel = 1000
    db_session.commit()
    corr = request_correction(db_session, trip, supervisor, "fuel", 1150, "OCR ผิด")
    approve_correction(db_session, corr, super_admin)
    with pytest.raises(CorrectionError):
        approve_correction(db_session, corr, super_admin)
    with pytest.raises(CorrectionError):
        reject_correction(db_session, corr, super_admin)


def test_correction_on_drop_allowance(db_session, driver, supervisor, super_admin):
    """แก้เบี้ยเลี้ยงรายจุดผ่าน field 'allowance:<dropId>'"""
    trip = _mk_trip(db_session, driver, n_drops=2)
    trip.frozen = True
    db_session.commit()
    drop = trip.drops[0]
    corr = request_correction(
        db_session, trip, supervisor, f"allowance:{drop.id}", 500, "จ่ายเพิ่มค่ารอ"
    )
    assert corr.old_val == 300
    approve_correction(db_session, corr, super_admin)
    db_session.refresh(drop)
    assert drop.allowance == 500
