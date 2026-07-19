"""Unit tests: Maintenance Report — คนขับแจ้งเหตุ/รถมีปัญหา ตอนรองาน (สถานะขาว)

- แจ้งเหตุ → เปิดเหตุ + ตั้งรถ MAINTENANCE + แจ้งเตือน (kind=VEHICLE_ISSUE)
- รถ MAINTENANCE → คุมงานจ่ายงานไม่ได้ (assign 400)
- ระหว่างมีทริปวิ่ง (ORANGE/GREEN) → แจ้งเหตุนี้ไม่ได้ (ให้ใช้ SOS)
- ปิดเหตุ → ตั้งรถกลับ AVAILABLE (เว้นแต่ยังมีเหตุอื่นค้าง)
"""
import pytest

from app.models import MaintenanceReport, Notification, Role, Trip, User, Vehicle
from app.models.enums import IncidentStatus, TripStatus, VehicleStatus
from app.services.maintenance import MaintenanceError, report_issue, resolve_report
from app.services.state_machine import assign_trip, finish_loading
from tests.conftest import ODO_PHOTO, pass_inspection

# รูป 1x1 png ถูกต้อง (base64) — save_photo_b64 ต้อง decode ได้
PNG_1PX = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="


@pytest.fixture()
def driver(db_session):
    return db_session.query(User).filter(User.emp_id == "D01").first()


@pytest.fixture()
def supervisor(db_session):
    from app.security import hash_password
    sv = User(emp_id="SV01", name="ธนพล คุมงาน", phone="0820000001",
              role=Role.SUPERVISOR, active=True, password_hash=hash_password("1234"))
    db_session.add(sv)
    db_session.commit()
    return sv


@pytest.fixture()
def vehicle(db_session, driver):
    v = Vehicle(plate="1กก-1234", model="ISUZU", driver_id=driver.id)
    db_session.add(v)
    db_session.commit()
    db_session.refresh(v)
    return v


def test_report_locks_vehicle_and_alerts(db_session, driver, vehicle):
    rep = report_issue(db_session, driver, message="ยางแบนล้อหน้าซ้าย", photo_b64=PNG_1PX)
    assert rep.status is IncidentStatus.OPEN
    assert rep.vehicle_id == vehicle.id
    assert rep.plate == "1กก-1234"
    assert rep.photo and rep.photo.startswith("/uploads/")
    db_session.refresh(vehicle)
    assert vehicle.status is VehicleStatus.MAINTENANCE
    assert db_session.query(Notification).filter_by(kind="VEHICLE_ISSUE").count() == 1


def test_report_without_vehicle_still_logs(db_session, driver):
    rep = report_issue(db_session, driver, message="ไฟหน้าไม่ติด", photo_b64=PNG_1PX)
    assert rep.status is IncidentStatus.OPEN
    assert rep.vehicle_id is None
    assert rep.plate == ""


def test_report_blocked_while_running(db_session, driver, supervisor, vehicle):
    trip = Trip(code="T-500", driver_id=driver.id)
    db_session.add(trip)
    db_session.commit()
    from app.models import Drop
    db_session.add(Drop(trip_id=trip.id, seq=1, name="จุด 1", allowance=300))
    db_session.commit()
    assign_trip(db_session, trip, vehicle.plate, supervisor)
    pass_inspection(db_session, trip, driver)
    finish_loading(db_session, trip, driver, 13.75, 100.5, odometer_start=1000, odometer_photo_b64=ODO_PHOTO)
    assert trip.status is TripStatus.GREEN
    with pytest.raises(MaintenanceError):
        report_issue(db_session, driver, message="x", photo_b64=PNG_1PX)


def test_resolve_unlocks_vehicle(db_session, driver, supervisor, vehicle):
    rep = report_issue(db_session, driver, message="เบรกหลวม", photo_b64=PNG_1PX)
    resolve_report(db_session, rep, supervisor, note="ซ่อมเบรกแล้ว")
    assert rep.status is IncidentStatus.RESOLVED
    db_session.refresh(vehicle)
    assert vehicle.status is VehicleStatus.AVAILABLE


def test_resolve_keeps_maintenance_when_other_open(db_session, driver, supervisor, vehicle):
    r1 = report_issue(db_session, driver, message="ยางแบน", photo_b64=PNG_1PX)
    r2 = report_issue(db_session, driver, message="ไฟเบรกเสีย", photo_b64=PNG_1PX)
    resolve_report(db_session, r1, supervisor)
    db_session.refresh(vehicle)
    assert vehicle.status is VehicleStatus.MAINTENANCE   # ยังมี r2 ค้าง
    resolve_report(db_session, r2, supervisor)
    db_session.refresh(vehicle)
    assert vehicle.status is VehicleStatus.AVAILABLE


def test_resolve_twice_rejected(db_session, driver, supervisor, vehicle):
    rep = report_issue(db_session, driver, message="เครื่องร้อน", photo_b64=PNG_1PX)
    resolve_report(db_session, rep, supervisor)
    with pytest.raises(MaintenanceError):
        resolve_report(db_session, rep, supervisor)


def test_assign_blocked_when_vehicle_in_maintenance(client, db_session, driver, supervisor, vehicle):
    from tests.conftest import login
    # คนขับแจ้งเหตุ → รถ MAINTENANCE
    report_issue(db_session, driver, message="ยางแบน", photo_b64=PNG_1PX)
    # สร้างทริป WHITE ให้คนขับคนนี้
    trip = Trip(code="T-600", driver_id=driver.id)
    db_session.add(trip)
    db_session.commit()
    from app.models import Drop
    db_session.add(Drop(trip_id=trip.id, seq=1, name="จุด 1", allowance=300))
    db_session.commit()

    # คุมงานล็อกอินแล้วจ่ายงาน — ต้องโดน 400 (รถกำลังซ่อม)
    r = login(client, "SV01")
    assert r.status_code == 200
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    resp = client.post(f"/trips/{trip.id}/assign", json={}, headers=headers)
    assert resp.status_code == 400
    assert "กำลังซ่อม" in resp.json()["detail"]
