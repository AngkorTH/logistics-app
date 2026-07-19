"""Unit tests: Storage Layer (Phase 4) — เก็บไฟล์รูปหลักฐานจริงจาก Base64"""
from pathlib import Path

import pytest

from app.models import Drop, Trip, User
from app.models.enums import ReceiptKind, Role
from app.services.evidence import upload_receipt, upload_tarp
from app.services.state_machine import assign_trip, finish_loading, record_delivery
from app.services.storage import UPLOAD_DIR, StorageError, save_photo_b64
from tests.conftest import ODO_PHOTO, pass_inspection

TINY_PNG = ("data:image/png;base64,"
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
            "/x8AAwMCAO+ip1sAAAAASUVORK5CYII=")


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


def _green_trip(db, driver, supervisor):
    trip = Trip(code="T-700", driver_id=driver.id)
    db.add(trip)
    db.commit()
    db.add(Drop(trip_id=trip.id, seq=1, name="จุด 1", allowance=300))
    db.commit()
    db.refresh(trip)
    assign_trip(db, trip, "1กก-1234", supervisor)
    pass_inspection(db, trip, driver)
    finish_loading(db, trip, driver, 13.75, 100.5, odometer_start=1000, odometer_photo_b64=ODO_PHOTO)
    return trip


def _file_of(url: str) -> Path:
    return UPLOAD_DIR / url.split("/")[-1]


# ---------------------------- save_photo_b64 ----------------------------
def test_save_b64_writes_file_and_returns_url():
    url = save_photo_b64(TINY_PNG, "test")
    assert url.startswith("/uploads/test-") and url.endswith(".png")
    assert _file_of(url).exists() and _file_of(url).stat().st_size > 0


def test_save_none_returns_none():
    assert save_photo_b64(None, "x") is None
    assert save_photo_b64("  ", "x") is None


def test_save_invalid_b64_raises():
    with pytest.raises(StorageError):
        save_photo_b64("data:image/png;base64,@@@ไม่ใช่b64@@@", "x")
    with pytest.raises(StorageError):
        save_photo_b64("data:image/bmp;base64,AAAA", "x")  # ชนิดไม่รองรับ


# ---------------------------- ผูกกับ business flow ----------------------------
def test_delivery_stores_real_photo(db_session, driver, supervisor):
    trip = _green_trip(db_session, driver, supervisor)
    drop = trip.drops[0]
    record_delivery(db_session, drop, driver, 13.8, 100.6, photo_b64=TINY_PNG)
    assert drop.photo.startswith("/uploads/dlv-")
    assert _file_of(drop.photo).exists()


def test_delivery_without_photo_still_marks(db_session, driver, supervisor):
    """ไม่ส่งรูป (flow เก่า/offline เพี้ยน) → ยังนับหลักฐานเป็น 'attached' เหมือนเดิม"""
    trip = _green_trip(db_session, driver, supervisor)
    drop = trip.drops[0]
    record_delivery(db_session, drop, driver, 13.8, 100.6)
    assert drop.photo == "attached"


def test_tarp_and_receipt_store_photos(db_session, driver, supervisor):
    trip = _green_trip(db_session, driver, supervisor)
    drop = trip.drops[0]
    upload_tarp(db_session, drop, driver, photo_b64=TINY_PNG)
    assert drop.tarp.startswith("/uploads/tarp-")

    r = upload_receipt(db_session, drop, driver, ReceiptKind.FUEL,
                       ocr_amount=500, photo_b64=TINY_PNG)
    assert r.photo.startswith("/uploads/rcpt-")
    assert _file_of(r.photo).exists()


def test_uploads_served_via_static(db_session, driver, supervisor):
    """ไฟล์ที่เก็บต้องเปิดผ่าน /uploads/<ชื่อ> ได้จริง (StaticFiles)"""
    from fastapi.testclient import TestClient
    from app.main import app

    url = save_photo_b64(TINY_PNG, "serve")
    client = TestClient(app)
    res = client.get(url)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("image/")
