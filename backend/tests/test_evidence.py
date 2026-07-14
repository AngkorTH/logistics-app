"""Unit tests: Multi-Drop & Evidence (หลักฐาน 4 ปุ่มรายจุด + OCR draft)

ครอบคลุม: อัปบิลน้ำมัน/ทางหลวงแยกรายจุด, OCR ตั้ง draft (ไม่ auto-commit),
อัปซ้ำรีเซ็ต draft, อนุมัติบิล, รูปผ้าใบ, และการ์ด freeze
"""
import pytest

from app.models import Drop, Trip, User
from app.models.enums import ReceiptKind, Role, TripStatus
from app.services.evidence import (
    EvidenceError,
    approve_receipt,
    upload_receipt,
    upload_tarp,
)


def _mk_trip(db, driver, n_drops=3, status=TripStatus.GREEN):
    trip = Trip(code="T-020", driver_id=driver.id, status=status, distance_km=120)
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


def test_upload_receipt_is_ocr_draft_not_committed(db_session, driver, supervisor):
    """อัปบิลน้ำมัน → OCR ตั้งยอดเป็น draft (approved=False) ไม่ auto-commit"""
    trip = _mk_trip(db_session, driver)
    r = upload_receipt(db_session, trip.drops[0], supervisor, ReceiptKind.FUEL, ocr_amount=1250.5)
    assert r.kind is ReceiptKind.FUEL
    assert r.amount == 1250.5
    assert r.approved is False  # ห้าม auto-commit


def test_receipts_are_per_drop_and_kind(db_session, driver, supervisor):
    """แต่ละจุดแยกบิลของตัวเอง และแยกชนิดน้ำมัน/ทางหลวง — ไม่ตีกัน"""
    trip = _mk_trip(db_session, driver)
    upload_receipt(db_session, trip.drops[0], supervisor, ReceiptKind.FUEL, ocr_amount=1000)
    upload_receipt(db_session, trip.drops[0], supervisor, ReceiptKind.TOLL, ocr_amount=90)
    upload_receipt(db_session, trip.drops[1], supervisor, ReceiptKind.FUEL, ocr_amount=500)

    assert len(trip.drops[0].receipts) == 2   # น้ำมัน + ทางหลวง
    assert len(trip.drops[1].receipts) == 1
    assert len(trip.drops[2].receipts) == 0


def test_reupload_resets_draft(db_session, driver, supervisor):
    """อัปบิลซ้ำจุด+ชนิดเดิม = แก้ draft เดิม (ไม่สร้างใบซ้ำ) และรีเซ็ต approved=False"""
    trip = _mk_trip(db_session, driver)
    drop = trip.drops[0]
    r1 = upload_receipt(db_session, drop, supervisor, ReceiptKind.FUEL, ocr_amount=1000)
    approve_receipt(db_session, r1, supervisor)
    assert r1.approved is True

    r2 = upload_receipt(db_session, drop, supervisor, ReceiptKind.FUEL, ocr_amount=1100)
    assert r2.id == r1.id            # ใบเดิม
    assert r2.amount == 1100
    assert r2.approved is False      # อัปใหม่ต้องตรวจใหม่
    assert len(drop.receipts) == 1


def test_approve_receipt_can_override_amount(db_session, driver, supervisor):
    """Supervisor แก้ยอดตอนอนุมัติได้ (OCR อ่านเพี้ยน)"""
    trip = _mk_trip(db_session, driver)
    r = upload_receipt(db_session, trip.drops[0], supervisor, ReceiptKind.TOLL, ocr_amount=88)
    approve_receipt(db_session, r, supervisor, amount=95)
    assert r.approved is True
    assert r.amount == 95


def test_upload_tarp_sets_flag(db_session, driver, supervisor):
    trip = _mk_trip(db_session, driver)
    assert not trip.drops[0].tarp
    upload_tarp(db_session, trip.drops[0], driver)
    assert trip.drops[0].tarp  # Phase 4: เก็บ path/marker แทน bool


def test_no_ocr_amount_defaults_zero_for_manual_entry(db_session, driver, supervisor):
    """ไม่มีผล OCR → ยอด draft = 0 ให้ Supervisor กรอกเอง"""
    trip = _mk_trip(db_session, driver)
    r = upload_receipt(db_session, trip.drops[0], supervisor, ReceiptKind.FUEL)
    assert r.amount == 0.0
    assert r.approved is False


def test_cannot_upload_evidence_after_freeze(db_session, driver, supervisor):
    """ทริป freeze แล้ว แนบหลักฐานเพิ่มไม่ได้"""
    trip = _mk_trip(db_session, driver)
    trip.frozen = True
    db_session.commit()
    with pytest.raises(EvidenceError):
        upload_receipt(db_session, trip.drops[0], supervisor, ReceiptKind.FUEL, ocr_amount=100)
    with pytest.raises(EvidenceError):
        upload_tarp(db_session, trip.drops[0], driver)
