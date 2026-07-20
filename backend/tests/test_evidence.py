"""Unit tests: Multi-Drop & Evidence (หลักฐาน 4 ปุ่มรายจุด + OCR draft)

ครอบคลุม: อัปบิลน้ำมัน/ทางหลวงแยกรายจุด, OCR ตั้ง draft (ไม่ auto-commit),
อัปซ้ำรีเซ็ต draft, อนุมัติบิล, รูปผ้าใบ, และการ์ด freeze
"""
import pytest

from tests.conftest import PHOTO

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
        db.add(Drop(origin="ต้นทาง", destination="ปลายทาง", trip_id=trip.id, seq=i, name=f"จุด {i}", allowance=300))
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


def test_upload_receipt_is_blank_draft_no_ocr(db_session, driver, supervisor):
    """อัปบิล → draft เปล่า (ยอด 0 · ไม่มีวันที่) เพราะปิด OCR แล้ว · เก็บ URL รูปจริง"""
    trip = _mk_trip(db_session, driver)
    r = upload_receipt(db_session, trip.drops[0], supervisor, ReceiptKind.FUEL, photo_b64=PHOTO)
    assert r.kind is ReceiptKind.FUEL
    assert r.amount == 0.0       # ไม่มี OCR — รอ Supervisor กรอกเอง
    assert r.date is None
    assert r.photo.startswith("/uploads/rcpt-")  # เก็บ path ไฟล์จริง ไม่ใช่ marker
    assert r.approved is False   # ห้าม auto-commit


def test_upload_receipt_requires_photo(db_session, driver, supervisor):
    """ไม่มีรูปบิล = ตรวจยอดไม่ได้ → บล็อก"""
    trip = _mk_trip(db_session, driver)
    with pytest.raises(EvidenceError):
        upload_receipt(db_session, trip.drops[0], supervisor, ReceiptKind.FUEL)


def test_receipts_are_per_drop_and_kind(db_session, driver, supervisor):
    """แต่ละจุดแยกบิลของตัวเอง และแยกชนิดน้ำมัน/ทางหลวง — ไม่ตีกัน"""
    trip = _mk_trip(db_session, driver)
    upload_receipt(db_session, trip.drops[0], supervisor, ReceiptKind.FUEL, photo_b64=PHOTO)
    upload_receipt(db_session, trip.drops[0], supervisor, ReceiptKind.TOLL, photo_b64=PHOTO)
    upload_receipt(db_session, trip.drops[1], supervisor, ReceiptKind.FUEL, photo_b64=PHOTO)

    assert len(trip.drops[0].receipts) == 2   # น้ำมัน + ทางหลวง
    assert len(trip.drops[1].receipts) == 1
    assert len(trip.drops[2].receipts) == 0


def test_reupload_resets_draft(db_session, driver, supervisor):
    """อัปบิลซ้ำจุด+ชนิดเดิม = แก้ draft เดิม (ไม่สร้างใบซ้ำ) และรีเซ็ต approved=False"""
    trip = _mk_trip(db_session, driver)
    drop = trip.drops[0]
    r1 = upload_receipt(db_session, drop, supervisor, ReceiptKind.FUEL, photo_b64=PHOTO)
    approve_receipt(db_session, r1, supervisor, amount=1000, date="2026-07-10")
    assert r1.approved is True

    r2 = upload_receipt(db_session, drop, supervisor, ReceiptKind.FUEL, photo_b64=PHOTO)
    assert r2.id == r1.id            # ใบเดิม
    assert r2.amount == 0            # อัปใหม่ = ล้างยอดเดิม รอคีย์ใหม่
    assert r2.date is None
    assert r2.approved is False      # อัปใหม่ต้องตรวจใหม่
    assert len(drop.receipts) == 1


def test_approve_receipt_takes_manual_amount_and_date(db_session, driver, supervisor):
    """Supervisor เปิดรูปดูแล้วคีย์ยอด + วันที่เอง (แทน OCR)"""
    trip = _mk_trip(db_session, driver)
    r = upload_receipt(db_session, trip.drops[0], supervisor, ReceiptKind.TOLL, photo_b64=PHOTO)
    approve_receipt(db_session, r, supervisor, amount=95, date="2026-07-11")
    assert r.approved is True
    assert r.amount == 95
    assert r.date == "2026-07-11"


def test_approve_requires_both_amount_and_date(db_session, driver, supervisor):
    """ขาดวันที่ = ยืนยันบิลไม่ได้ (ไม่มี OCR มาเติมให้แล้ว)"""
    trip = _mk_trip(db_session, driver)
    r = upload_receipt(db_session, trip.drops[0], supervisor, ReceiptKind.TOLL, photo_b64=PHOTO)
    with pytest.raises(EvidenceError):
        approve_receipt(db_session, r, supervisor, amount=95, date="  ")
    assert r.approved is False


def test_upload_tarp_stores_real_file_path(db_session, driver, supervisor):
    """รูปผ้าใบเก็บ URL ไฟล์จริง — ไม่ใช่ marker "attached" หรือ boolean"""
    trip = _mk_trip(db_session, driver)
    assert not trip.drops[0].tarp
    upload_tarp(db_session, trip.drops[0], driver, photo_b64=PHOTO)
    assert trip.drops[0].tarp.startswith("/uploads/tarp-")


def test_upload_tarp_requires_photo(db_session, driver, supervisor):
    """ไม่มีรูป = บันทึกผ้าใบไม่ได้ (เลิกใช้ marker "attached")"""
    trip = _mk_trip(db_session, driver)
    with pytest.raises(EvidenceError):
        upload_tarp(db_session, trip.drops[0], driver)
    assert trip.drops[0].tarp is None


def test_cannot_upload_evidence_after_freeze(db_session, driver, supervisor):
    """ทริป freeze แล้ว แนบหลักฐานเพิ่มไม่ได้"""
    trip = _mk_trip(db_session, driver)
    trip.frozen = True
    db_session.commit()
    with pytest.raises(EvidenceError):
        upload_receipt(db_session, trip.drops[0], supervisor, ReceiptKind.FUEL, photo_b64=PHOTO)
    with pytest.raises(EvidenceError):
        upload_tarp(db_session, trip.drops[0], driver, photo_b64=PHOTO)
