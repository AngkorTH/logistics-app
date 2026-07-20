"""สรุปรวบยอดทั้งเที่ยว (trip_summary) + การ์ด "1 ขาต่อครั้ง"

- คนขับส่งของได้เฉพาะขาที่คนคุมงานจ่ายมา (GREEN) — จบขาแล้วต้องรอจ่ายงานใหม่
- สรุปเที่ยว: น้ำมันรวม · เลขไมล์ต้น→ปลาย · จำนวนขา · เส้นทางเรียงลำดับ
"""
import pytest

from app.models import Drop, Trip, User
from app.models.enums import Role, TripDifficulty, TripStatus
from app.security import hash_password
from app.services.evidence import log_fuel
from app.services.finance import trip_summary
from app.services.state_machine import (
    TransitionError,
    add_drop,
    assign_trip,
    complete_trip,
    end_trip,
    finish_loading,
    record_delivery,
)
from tests.conftest import PHOTO, ODO_PHOTO, pass_inspection


@pytest.fixture()
def driver(db_session):
    return db_session.query(User).filter(User.emp_id == "D01").first()


@pytest.fixture()
def supervisor(db_session):
    sv = User(emp_id="SV01", name="ธนพล คุมงาน", phone="0820000001",
              role=Role.SUPERVISOR, active=True, password_hash=hash_password("1234"))
    db_session.add(sv)
    db_session.commit()
    return sv


def _trip_with_first_leg(db, driver, supervisor):
    """เที่ยวที่จ่ายขาแรกแล้ว กำลังวิ่ง (GREEN)"""
    trip = Trip(code="T-SUM", driver_id=driver.id, distance_km=0)
    db.add(trip)
    db.commit()
    db.add(Drop(trip_id=trip.id, seq=1, name="ลำปาง → กรุงเทพฯ",
                origin="ลำปาง", destination="กรุงเทพฯ", allowance=500))
    db.commit()
    db.refresh(trip)
    assign_trip(db, trip, "1กก-1234", supervisor)
    pass_inspection(db, trip, driver)
    finish_loading(db, trip, driver, 13.75, 100.5,
                   odometer_start=1000, odometer_photo_b64=ODO_PHOTO, loaded_photo_b64=PHOTO)
    return trip


def _next_leg(db, trip, driver, supervisor, origin, destination):
    """คนคุมงานจ่ายขาถัดไป → คนขับขึ้นของแล้ววิ่งต่อ"""
    add_drop(db, trip, supervisor, origin=origin, destination=destination, revenue=10000)
    assign_trip(db, trip, "1กก-1234", supervisor)
    finish_loading(db, trip, driver, 13.75, 100.5, loaded_photo_b64=PHOTO)


def test_driver_cannot_start_next_leg_alone(db_session, driver, supervisor):
    """จบขาแล้วคนขับกลับเป็น "รองาน" — วิ่งขาถัดไปเองไม่ได้จนกว่าคนคุมงานจะจ่ายงานใหม่"""
    trip = _trip_with_first_leg(db_session, driver, supervisor)
    record_delivery(db_session, trip.drops[0], driver, 13.8, 100.6, photo_b64=PHOTO)
    assert trip.status is TripStatus.WHITE

    # คนคุมงานเพิ่มขาที่ 2 แต่ยังไม่จ่ายงาน → คนขับยังส่งไม่ได้
    add_drop(db_session, trip, supervisor, origin="กรุงเทพฯ", destination="ตาก", revenue=10000)
    with pytest.raises(TransitionError):
        record_delivery(db_session, trip.drops[1], driver, 13.8, 100.6, photo_b64=PHOTO)

    # จ่ายงานแล้ว → วิ่งต่อได้
    assign_trip(db_session, trip, "1กก-1234", supervisor)
    finish_loading(db_session, trip, driver, 13.75, 100.5, loaded_photo_b64=PHOTO)
    record_delivery(db_session, trip.drops[1], driver, 13.8, 100.6, photo_b64=PHOTO)
    assert trip.status is TripStatus.WHITE
    assert trip.completed_at is None      # เที่ยวหลักยังไม่จบ


def test_redelivery_is_idempotent_after_status_flips_white(db_session, driver, supervisor):
    """กดส่งซ้ำหลังทริปพลิกเป็น WHITE ต้องเงียบ (ไม่ error)"""
    trip = _trip_with_first_leg(db_session, driver, supervisor)
    d = trip.drops[0]
    record_delivery(db_session, d, driver, 13.8, 100.6, photo_b64=PHOTO)
    assert record_delivery(db_session, d, driver, 13.8, 100.6, photo_b64=PHOTO) is d


def test_summary_rolls_up_whole_trip(db_session, driver, supervisor):
    """สรุปเที่ยว: จำนวนขา · น้ำมันรวม · เลขไมล์ต้น→ปลาย · เส้นทางเรียงลำดับ"""
    trip = _trip_with_first_leg(db_session, driver, supervisor)
    log_fuel(db_session, trip, driver, liters=40, photo_b64=ODO_PHOTO)
    record_delivery(db_session, trip.drops[0], driver, 13.8, 100.6, photo_b64=PHOTO)

    _next_leg(db_session, trip, driver, supervisor, "กรุงเทพฯ", "ตาก")
    log_fuel(db_session, trip, driver, liters=20, photo_b64=ODO_PHOTO)
    record_delivery(db_session, trip.drops[1], driver, 13.8, 100.6, photo_b64=PHOTO)

    _next_leg(db_session, trip, driver, supervisor, "ตาก", "สระบุรี")
    record_delivery(db_session, trip.drops[2], driver, 13.8, 100.6, photo_b64=PHOTO)

    end_trip(db_session, trip, driver, 1600, odometer_photo_b64=PHOTO)      # เลขไมล์ปลายเที่ยว
    complete_trip(db_session, trip, supervisor)   # คนคุมงานกดจบเที่ยว

    s = trip_summary(trip)
    assert s["legs"] == 3 and s["legs_total"] == 3
    assert s["fuel_liters"] == 60.0
    assert s["odometer_start"] == 1000 and s["odometer_end"] == 1600
    assert s["total_km"] == 600
    assert s["km_per_liter"] == 10.0              # 600 / 60
    assert [(r["origin"], r["destination"]) for r in s["route"]] == [
        ("ลำปาง", "กรุงเทพฯ"),
        ("กรุงเทพฯ", "ตาก"),
        ("ตาก", "สระบุรี"),
    ]


def test_end_trip_does_not_complete_the_trip(db_session, driver, supervisor):
    """คนขับบันทึกเลขไมล์ปลายเที่ยว ไม่ถือว่า "จบเที่ยว" — ยังต้องให้คนคุมงานกด"""
    trip = _trip_with_first_leg(db_session, driver, supervisor)
    record_delivery(db_session, trip.drops[0], driver, 13.8, 100.6, photo_b64=PHOTO)
    end_trip(db_session, trip, driver, 1200, odometer_photo_b64=PHOTO)

    assert trip.odometer_end == 1200
    assert trip.completed_at is None
    assert trip.closed_at is None


def test_summary_in_trip_detail_api(client, db_session, driver, supervisor):
    trip = _trip_with_first_leg(db_session, driver, supervisor)
    token = client.post("/auth/login",
                        json={"identifier": "D01", "password": "1234"}).json()["access_token"]
    body = client.get(f"/trips/{trip.id}",
                      headers={"Authorization": f"Bearer {token}"}).json()
    assert body["summary"]["legs_total"] == 1
    assert body["summary"]["route"][0]["origin"] == "ลำปาง"


# --------------------- สูตรเบี้ยเลี้ยง: รายได้ต่อขา × %ความยาก ---------------------
@pytest.mark.parametrize("difficulty,expected", [
    (TripDifficulty.EASY, 500.0),     # 10000 × 5%
    (TripDifficulty.MEDIUM, 700.0),   # 10000 × 7%
    (TripDifficulty.HARD, 1000.0),    # 10000 × 10%
])
def test_allowance_from_revenue_and_difficulty(db_session, driver, supervisor, difficulty, expected):
    trip = Trip(code=f"T-RV{difficulty.value}", driver_id=driver.id)
    db_session.add(trip)
    db_session.commit()
    drop = add_drop(db_session, trip, supervisor, origin="ลำปาง", destination="กรุงเทพฯ",
                    revenue=10000, difficulty=difficulty)
    assert drop.revenue == 10000
    assert drop.difficulty is difficulty
    assert drop.allowance == expected


def test_add_drop_requires_revenue(db_session, driver, supervisor):
    trip = Trip(code="T-RV0", driver_id=driver.id)
    db_session.add(trip)
    db_session.commit()
    with pytest.raises(TransitionError):
        add_drop(db_session, trip, supervisor, origin="ก", destination="ข", revenue=0)


def test_create_trip_api_computes_allowance(client, db_session, driver, supervisor):
    """POST /trips — บังคับ revenue และคิดเบี้ยเลี้ยงให้เอง (ไม่รับ allowance จากผู้ใช้)"""
    sv_token = client.post("/auth/login",
                           json={"identifier": "SV01", "password": "1234"}).json().get("access_token")
    headers = {"Authorization": f"Bearer {sv_token}"}
    payload = {
        "driver_id": driver.id, "distance_km": 100,
        "drops": [{"origin": "ลำปาง", "destination": "กรุงเทพฯ",
                   "revenue": 20000, "difficulty": "HARD"}],
    }
    r = client.post("/trips", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["drops"][0]["allowance"] == 2000.0    # 20000 × 10%

    # ไม่ส่ง revenue → 422
    bad = {"driver_id": driver.id, "drops": [{"origin": "ก", "destination": "ข"}]}
    assert client.post("/trips", json=bad, headers=headers).status_code == 422
