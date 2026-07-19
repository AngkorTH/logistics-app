"""Unit tests: Advance Payment (ข้อ 1.3)

โฟกัสตามที่ผู้ใช้กำชับ: ยอด APPROVED ต้องถูก "หักลบ" กับยอดจ่ายสุทธิ
ตอนล็อกการเงิน (close_trip) อย่างถูกต้อง และห้ามหักซ้ำ
"""
import pytest

from app.models import Advance, Drop, Trip, User
from app.models.enums import AdvanceStatus, Role, TripStatus
from app.services.advance import (
    AdvanceError,
    decide_advance,
    request_advance,
)
from app.services.finance import compute_finance
from app.services.state_machine import (
    assign_trip,
    close_trip,
    complete_trip,
    finish_loading,
    record_delivery,
)
from tests.conftest import ODO_PHOTO, pass_inspection


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


def _mk_trip(db, driver, code="T-200", n_drops=2, allowance=300):
    trip = Trip(code=code, driver_id=driver.id)
    db.add(trip)
    db.commit()
    for i in range(1, n_drops + 1):
        db.add(Drop(trip_id=trip.id, seq=i, name=f"จุด {i}", allowance=allowance))
    db.commit()
    db.refresh(trip)
    return trip


def _run_to_delivered(db, trip, driver, supervisor):
    assign_trip(db, trip, "1กก-1234", supervisor)
    pass_inspection(db, trip, driver)
    finish_loading(db, trip, driver, 13.75, 100.5, odometer_start=1000, odometer_photo_b64=ODO_PHOTO)
    for d in trip.drops:
        record_delivery(db, d, driver, 13.8, 100.6)
    # flow ใหม่: เที่ยวหลักจบสมบูรณ์เมื่อ Supervisor กด "จบเที่ยว" เท่านั้น
    complete_trip(db, trip, supervisor)


# ------------------------------ validations ------------------------------
def test_request_validations(db_session, driver):
    with pytest.raises(AdvanceError):
        request_advance(db_session, driver, 0, "เหตุผล")
    with pytest.raises(AdvanceError):
        request_advance(db_session, driver, 500, "  ")


def test_request_binds_active_trip(db_session, driver, supervisor):
    trip = _mk_trip(db_session, driver)
    assign_trip(db_session, trip, "1กก-1234", supervisor)  # ORANGE = กำลังวิ่ง
    adv = request_advance(db_session, driver, 500, "ค่าน้ำมันสำรอง")
    assert adv.trip_id == trip.id
    assert adv.status is AdvanceStatus.PENDING


def test_decide_once_only(db_session, driver, supervisor):
    adv = request_advance(db_session, driver, 300, "ค่าอาหาร")
    decide_advance(db_session, adv, supervisor, approve=False)
    assert adv.status is AdvanceStatus.REJECTED
    with pytest.raises(AdvanceError):
        decide_advance(db_session, adv, supervisor, approve=True)


# --------------------------- deduction on close ---------------------------
def test_close_trip_deducts_approved_advance(db_session, driver, supervisor):
    """เบี้ยเลี้ยง 600 · เบิกอนุมัติ 500 → payout สุทธิ 100 และ advance ถูกประทับหัก"""
    trip = _mk_trip(db_session, driver)  # 2 จุด x 300 = 600
    _run_to_delivered(db_session, trip, driver, supervisor)

    adv = request_advance(db_session, driver, 500, "ค่าน้ำมันสำรอง")
    decide_advance(db_session, adv, supervisor, approve=True)

    # พรีวิวก่อนล็อก: advance_total ต้องโผล่แล้ว
    fin = compute_finance(trip)
    assert fin.advance_total == 500
    assert fin.payout_net == 600 - 500  # ไม่มีบิลน้ำมัน/ทางหลวง

    close_trip(db_session, trip, supervisor)
    db_session.refresh(adv)
    assert adv.deducted_trip_id == trip.id
    assert adv.deducted_at is not None

    # หลังล็อก: snapshot ถาวรต้องได้ค่าเดิม
    fin = compute_finance(trip)
    assert fin.advance_total == 500
    assert fin.payout_net == 100


def test_no_double_deduction_on_next_trip(db_session, driver, supervisor):
    """ยอดที่หักไปแล้วต้องไม่ถูกหักซ้ำกับทริปถัดไป"""
    t1 = _mk_trip(db_session, driver, code="T-201")
    _run_to_delivered(db_session, t1, driver, supervisor)
    adv = request_advance(db_session, driver, 400, "ค่าที่พัก")
    decide_advance(db_session, adv, supervisor, approve=True)
    close_trip(db_session, t1, supervisor)

    t2 = _mk_trip(db_session, driver, code="T-202")
    _run_to_delivered(db_session, t2, driver, supervisor)
    fin2 = compute_finance(t2)
    assert fin2.advance_total == 0
    close_trip(db_session, t2, supervisor)
    db_session.refresh(adv)
    assert adv.deducted_trip_id == t1.id  # ยังชี้ทริปแรกเท่านั้น


def test_pending_and_rejected_not_deducted(db_session, driver, supervisor):
    trip = _mk_trip(db_session, driver, code="T-203")
    _run_to_delivered(db_session, trip, driver, supervisor)

    pend = request_advance(db_session, driver, 100, "รอตัดสิน")
    rej = request_advance(db_session, driver, 200, "โดนปฏิเสธ")
    decide_advance(db_session, rej, supervisor, approve=False)

    close_trip(db_session, trip, supervisor)
    db_session.refresh(pend)
    db_session.refresh(rej)
    assert pend.deducted_trip_id is None
    assert rej.deducted_trip_id is None
    assert compute_finance(trip).advance_total == 0
