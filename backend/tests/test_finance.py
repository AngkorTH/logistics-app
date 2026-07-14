"""Unit tests: Financial Operations & Penalty

ครอบคลุม: รวมเบี้ยเลี้ยงหลายจุด, ยอดน้ำมัน/ทางหลวงนับเฉพาะ approved,
หักเงินบังคับเหตุผล, หักจากเบี้ยเลี้ยงเท่านั้น (ห้ามทะลุ), และการ์ด freeze
"""
import pytest

from app.models import Drop, Trip, User
from app.models.enums import ReceiptKind, Role, TripStatus
from app.services.evidence import approve_receipt, upload_receipt
from app.services.finance import (
    FinanceError,
    apply_penalty,
    compute_finance,
    set_bonus,
)


def _mk_trip(db, driver, allowances=(300, 300, 400), status=TripStatus.GREEN):
    trip = Trip(code="T-030", driver_id=driver.id, status=status, distance_km=120)
    db.add(trip)
    db.commit()
    db.refresh(trip)
    for i, a in enumerate(allowances, start=1):
        db.add(Drop(trip_id=trip.id, seq=i, name=f"จุด {i}", allowance=a))
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


def test_allowance_total_sums_all_drops(db_session, driver):
    trip = _mk_trip(db_session, driver, allowances=(300, 300, 400))
    fin = compute_finance(trip)
    assert fin.allowance_total == 1000
    assert fin.allowance_net == 1000  # ยังไม่หัก


def test_fuel_toll_counts_only_approved(db_session, driver, supervisor):
    """ยอดน้ำมัน/ทางหลวงคิดเฉพาะบิลที่ approved — draft ไม่นับ"""
    trip = _mk_trip(db_session, driver)
    r1 = upload_receipt(db_session, trip.drops[0], supervisor, ReceiptKind.FUEL, ocr_amount=1000)
    upload_receipt(db_session, trip.drops[1], supervisor, ReceiptKind.FUEL, ocr_amount=500)  # draft
    upload_receipt(db_session, trip.drops[0], supervisor, ReceiptKind.TOLL, ocr_amount=90)   # draft

    fin = compute_finance(trip)
    assert fin.fuel_total == 0 and fin.toll_total == 0  # ยังไม่ approve เลย

    approve_receipt(db_session, r1, supervisor)
    fin = compute_finance(trip)
    assert fin.fuel_total == 1000  # นับเฉพาะใบที่ approve
    assert fin.toll_total == 0


def test_penalty_requires_reason(db_session, driver, supervisor):
    trip = _mk_trip(db_session, driver)
    with pytest.raises(FinanceError):
        apply_penalty(db_session, trip, supervisor, 200, "")
    with pytest.raises(FinanceError):
        apply_penalty(db_session, trip, supervisor, 200, "   ")
    assert trip.penalty == 0


def test_penalty_deducts_from_allowance_only(db_session, driver, supervisor):
    """หักจากเบี้ยเลี้ยงรวม → allowance_net ลดลง แต่ fuel/toll ไม่ถูกแตะ"""
    trip = _mk_trip(db_session, driver, allowances=(300, 300, 400))  # รวม 1000
    apply_penalty(db_session, trip, supervisor, 250, "ส่งช้ากว่ากำหนด")
    fin = compute_finance(trip)
    assert trip.penalty == 250
    assert trip.penalty_reason == "ส่งช้ากว่ากำหนด"
    assert fin.allowance_net == 750  # 1000 - 250


def test_penalty_cannot_exceed_allowance_ceiling(db_session, driver, supervisor):
    """หักเกินเบี้ยเลี้ยงรวม+โบนัส ไม่ได้ (ห้ามทะลุเข้าค่าน้ำมัน/เงินเดือน)"""
    trip = _mk_trip(db_session, driver, allowances=(300, 300, 400))  # รวม 1000
    with pytest.raises(FinanceError):
        apply_penalty(db_session, trip, supervisor, 1500, "หักเยอะเกิน")
    assert trip.penalty == 0  # ไม่ถูกตั้ง


def test_penalty_ceiling_includes_bonus(db_session, driver, supervisor):
    trip = _mk_trip(db_session, driver, allowances=(300, 300, 400))  # 1000
    set_bonus(db_session, trip, supervisor, 200)  # เพดานเป็น 1200
    apply_penalty(db_session, trip, supervisor, 1200, "หักเต็มเพดาน")
    fin = compute_finance(trip)
    assert fin.allowance_net == 0


def test_negative_penalty_rejected(db_session, driver, supervisor):
    trip = _mk_trip(db_session, driver)
    with pytest.raises(FinanceError):
        apply_penalty(db_session, trip, supervisor, -50, "ติดลบ")


def test_finance_locked_after_freeze(db_session, driver, supervisor):
    """freeze แล้ว แก้ penalty/bonus ไม่ได้"""
    trip = _mk_trip(db_session, driver)
    trip.frozen = True
    db_session.commit()
    with pytest.raises(FinanceError):
        apply_penalty(db_session, trip, supervisor, 100, "หลัง freeze")
    with pytest.raises(FinanceError):
        set_bonus(db_session, trip, supervisor, 100)
