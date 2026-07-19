"""Unit tests: แจ้งเติมน้ำมันระหว่างทริป + คำนวณอัตราสิ้นเปลือง km/L

ครอบคลุม: บันทึกลิตรหลายครั้งต่อทริป, สูตร km/L = ระยะทาง/ลิตรรวม ปัด 1 ตำแหน่ง,
กันหารศูนย์ (ลิตรรวม 0 → None), การ์ดเลขไมล์จบ < เลขไมล์เริ่ม, และการ์ด freeze
"""
import pytest

from app.models import Drop, Trip, User
from app.models.enums import ReceiptKind, Role, TripStatus
from app.services.evidence import EvidenceError, log_fuel
from app.services.finance import total_liters
from app.services.state_machine import (
    TransitionError,
    TransitionWarning,
    compute_km_per_liter,
    end_trip,
)

PNG_B64 = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _mk_trip(db, driver, *, odometer_start=1000.0, n_drops=2, delivered=True):
    trip = Trip(
        code="T-090", driver_id=driver.id, status=TripStatus.GREEN,
        distance_km=0, odometer_start=odometer_start,
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    for i in range(1, n_drops + 1):
        db.add(Drop(trip_id=trip.id, seq=i, name=f"จุด {i}", allowance=300, delivered=delivered))
    db.commit()
    db.refresh(trip)
    return trip


@pytest.fixture()
def driver(db_session):
    return db_session.query(User).filter(User.emp_id == "D01").first()


def test_log_fuel_creates_draft_receipt_with_liters(db_session, driver):
    trip = _mk_trip(db_session, driver)
    r = log_fuel(db_session, trip, driver, liters=25.5, photo_b64=PNG_B64, ocr_amount=800)

    assert r.kind is ReceiptKind.FUEL
    assert r.liters == 25.5
    assert r.approved is False          # ยอดเงินยังเป็น draft รอ Supervisor
    assert r.drop_id is None and r.trip_id == trip.id
    assert r.photo and r.photo.startswith("/uploads/")


def test_multiple_fuel_logs_sum_liters(db_session, driver):
    trip = _mk_trip(db_session, driver)
    log_fuel(db_session, trip, driver, liters=20, photo_b64=PNG_B64)
    log_fuel(db_session, trip, driver, liters=10.25, photo_b64=PNG_B64)
    db_session.refresh(trip)

    assert total_liters(trip) == 30.25


def test_log_fuel_rejects_zero_liters(db_session, driver):
    trip = _mk_trip(db_session, driver)
    with pytest.raises(EvidenceError):
        log_fuel(db_session, trip, driver, liters=0, photo_b64=PNG_B64)


def test_end_trip_computes_km_per_liter(db_session, driver):
    trip = _mk_trip(db_session, driver, odometer_start=1000)
    log_fuel(db_session, trip, driver, liters=20, photo_b64=PNG_B64)
    db_session.refresh(trip)

    end_trip(db_session, trip, driver, 1250)

    assert trip.odometer_end == 1250
    assert trip.distance_km == 250            # 1250 − 1000
    assert trip.km_per_liter == 12.5          # 250 / 20 ปัด 1 ตำแหน่ง
    # บันทึกเลขไมล์ปลายเที่ยวไม่ปิดเที่ยว — "จบเที่ยว" เป็นหน้าที่คนคุมงาน (complete_trip)
    assert trip.completed_at is None and trip.closed_at is None


def test_km_per_liter_rounds_to_one_decimal(db_session, driver):
    trip = _mk_trip(db_session, driver, odometer_start=0)
    log_fuel(db_session, trip, driver, liters=3, photo_b64=PNG_B64)
    db_session.refresh(trip)

    end_trip(db_session, trip, driver, 100)
    assert trip.km_per_liter == 33.3          # 100/3 = 33.333…


def test_zero_liters_gives_none_not_division_error(db_session, driver):
    trip = _mk_trip(db_session, driver, odometer_start=1000)
    end_trip(db_session, trip, driver, 1250)

    assert trip.km_per_liter is None          # ไม่มีบิลน้ำมัน → คิดไม่ได้ ไม่ใช่ ZeroDivisionError
    assert trip.distance_km == 250


def test_end_odometer_less_than_start_blocked(db_session, driver):
    trip = _mk_trip(db_session, driver, odometer_start=1000)
    with pytest.raises(TransitionError):
        end_trip(db_session, trip, driver, 900)


def test_end_trip_warns_when_drops_not_delivered(db_session, driver):
    trip = _mk_trip(db_session, driver, odometer_start=1000, delivered=False)
    with pytest.raises(TransitionWarning):
        end_trip(db_session, trip, driver, 1200)

    end_trip(db_session, trip, driver, 1200, force=True)   # ยืนยันแล้วทำได้
    assert trip.odometer_end == 1200 and trip.override is True


def test_frozen_trip_rejects_fuel_and_end(db_session, driver):
    trip = _mk_trip(db_session, driver)
    trip.frozen = True
    db_session.commit()

    with pytest.raises(EvidenceError):
        log_fuel(db_session, trip, driver, liters=10, photo_b64=PNG_B64)
    with pytest.raises(TransitionError):
        end_trip(db_session, trip, driver, 1200)


def test_compute_falls_back_to_distance_km_without_odometer(db_session, driver):
    trip = _mk_trip(db_session, driver, odometer_start=None)
    trip.distance_km = 180
    db_session.commit()
    log_fuel(db_session, trip, driver, liters=15, photo_b64=PNG_B64)
    db_session.refresh(trip)

    assert compute_km_per_liter(trip) == 12.0   # 180 / 15


def test_fuel_and_end_trip_via_api(client, db_session, driver):
    trip = _mk_trip(db_session, driver, odometer_start=500)
    token = client.post(
        "/auth/login", json={"identifier": "D01", "password": "1234"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post(
        f"/trips/{trip.id}/fuel",
        json={"photo_b64": PNG_B64, "liters": 40, "ocr_amount": 1280},
        headers=headers,
    )
    assert r.status_code == 200 and r.json()["liters"] == 40

    r = client.post(f"/trips/{trip.id}/end", json={"odometer_end": 900}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["odometer_end"] == 900
    assert body["km_per_liter"] == 10.0        # 400 / 40
