"""Unit tests: บังคับเลขไมล์เริ่ม + รูปหน้าปัดไมล์ ตอน "ส่งผลตรวจสภาพรถก่อนวิ่ง"

ด่านย้ายมาอยู่ที่ submit_inspection: ขาดเลขไมล์/รูป = ส่งผลตรวจไม่ได้
ค่าถูกเขียนลงทริปทันที · ปุ่มขึ้นของเสร็จใช้ค่าที่บันทึกไว้ ไม่ถามซ้ำ
"""
import pytest

from app.models import Drop, Trip, User
from app.models.enums import TripStatus
from app.services.inspection import InspectionError, submit_inspection
from app.services.state_machine import TransitionError, finish_loading
from tests.conftest import PHOTO, ODO_PHOTO

OK_ITEMS = {"tires": True, "lights": True}


@pytest.fixture()
def driver(db_session):
    return db_session.query(User).filter(User.emp_id == "D01").first()


def _orange_trip(db, driver, code="T-100"):
    trip = Trip(code=code, driver_id=driver.id, status=TripStatus.ORANGE, plate="1กก-1234")
    db.add(trip)
    db.commit()
    db.refresh(trip)
    db.add(Drop(origin="ต้นทาง", destination="ปลายทาง", trip_id=trip.id, seq=1, name="จุด 1", allowance=300))
    db.commit()
    db.refresh(trip)
    return trip


def test_inspection_without_odometer_blocked(db_session, driver):
    trip = _orange_trip(db_session, driver)
    with pytest.raises(InspectionError):
        submit_inspection(db_session, trip, driver, OK_ITEMS,
                          odometer_start=None, odometer_photo_b64=ODO_PHOTO)


def test_inspection_without_photo_blocked(db_session, driver):
    trip = _orange_trip(db_session, driver)
    with pytest.raises(InspectionError):
        submit_inspection(db_session, trip, driver, OK_ITEMS,
                          odometer_start=1000, odometer_photo_b64=None)


def test_inspection_saves_odometer_and_photo(db_session, driver):
    trip = _orange_trip(db_session, driver)
    submit_inspection(db_session, trip, driver, OK_ITEMS,
                      odometer_start=1234.5, odometer_photo_b64=ODO_PHOTO)

    assert trip.odometer_start == 1234.5
    assert trip.odometer_start_photo.startswith("/uploads/odo-")

    # ปุ่มขึ้นของเสร็จไม่ต้องส่งเลขไมล์ซ้ำ — ใช้ค่าที่บันทึกไว้
    finish_loading(db_session, trip, driver, 13.75, 100.5, loaded_photo_b64=PHOTO)
    assert trip.status is TripStatus.GREEN
    assert trip.odometer_start == 1234.5


def test_odometer_lower_than_previous_trip_blocked(db_session, driver):
    # เที่ยวก่อนหน้าจบที่ไมล์ 5000
    db_session.add(Trip(code="T-099", driver_id=driver.id, status=TripStatus.WHITE,
                        odometer_start=4800, odometer_end=5000))
    db_session.commit()

    trip = _orange_trip(db_session, driver)
    with pytest.raises(InspectionError):
        submit_inspection(db_session, trip, driver, OK_ITEMS,
                          odometer_start=4900, odometer_photo_b64=ODO_PHOTO)

    # เท่ากับเลขจบเที่ยวก่อน = ผ่าน (รถจอดอยู่กับที่)
    submit_inspection(db_session, trip, driver, OK_ITEMS,
                      odometer_start=5000, odometer_photo_b64=ODO_PHOTO)
    assert trip.odometer_start == 5000


def test_start_blocked_when_trip_has_no_odometer(db_session, driver):
    """ทริปที่ไม่เคยผ่านด่านเลขไมล์ (ข้อมูลเก่า) → กดขึ้นของเสร็จไม่ได้"""
    trip = _orange_trip(db_session, driver)
    with pytest.raises(TransitionError):
        finish_loading(db_session, trip, driver, 13.75, 100.5, loaded_photo_b64=PHOTO)


def test_api_inspection_requires_odometer_fields(client, db_session, driver):
    trip = _orange_trip(db_session, driver)
    token = client.post("/auth/login", json={"identifier": "D01", "password": "1234"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # ขาดเลขไมล์/รูป → schema ตีกลับ 422
    r = client.post(f"/trips/{trip.id}/inspection", json={"items": {"tires": True}}, headers=headers)
    assert r.status_code == 422

    # ครบ → 200 แล้วเลขไมล์ถูกบันทึกลงทริป
    r = client.post(
        f"/trips/{trip.id}/inspection",
        json={"items": {"tires": True}, "odometer_start": 800, "odometer_photo_b64": ODO_PHOTO},
        headers=headers,
    )
    assert r.status_code == 200 and r.json()["status"] == "PASSED"

    body = client.get(f"/trips/{trip.id}", headers=headers).json()
    assert body["odometer_start"] == 800
    assert body["odometer_start_photo"].startswith("/uploads/odo-")
