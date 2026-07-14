"""Unit tests: SOS / Incident (ข้อ 1.4)

- แจ้งเหตุ → pause ทริป + แจ้งเตือนแดง (kind=SOS)
- ระหว่าง pause: กดขนของเสร็จ / ส่งของ / ล็อกการเงิน ไม่ได้
- ปิดเหตุ → ปลด pause (เว้นแต่ยังมีเหตุอื่นค้าง)
"""
import pytest

from app.models import Drop, Notification, Role, Trip, User
from app.models.enums import IncidentKind, IncidentStatus, TripStatus
from app.services.incident import IncidentError, report_sos, resolve_incident
from app.services.state_machine import (
    TransitionError,
    assign_trip,
    close_trip,
    finish_loading,
    record_delivery,
)
from tests.conftest import pass_inspection


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


def _mk_green_trip(db, driver, supervisor, n_drops=2):
    trip = Trip(code="T-300", driver_id=driver.id)
    db.add(trip)
    db.commit()
    for i in range(1, n_drops + 1):
        db.add(Drop(trip_id=trip.id, seq=i, name=f"จุด {i}", allowance=300))
    db.commit()
    db.refresh(trip)
    assign_trip(db, trip, "1กก-1234", supervisor)
    pass_inspection(db, trip, driver)
    finish_loading(db, trip, driver, 13.75, 100.5)
    return trip


def test_sos_pauses_trip_and_alerts(db_session, driver, supervisor):
    trip = _mk_green_trip(db_session, driver, supervisor)
    inc = report_sos(
        db_session, trip, driver, IncidentKind.ACCIDENT,
        message="ยางระเบิด", gps="13.80000,100.60000", photo_b64="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=",
    )
    assert inc.status is IncidentStatus.OPEN
    assert trip.paused is True
    assert db_session.query(Notification).filter_by(kind="SOS").count() == 1

    # ระหว่าง pause ทำอะไรต่อไม่ได้เลย
    with pytest.raises(TransitionError):
        record_delivery(db_session, trip.drops[0], driver, 13.8, 100.6)
    with pytest.raises(TransitionError):
        close_trip(db_session, trip, supervisor, force=True)


def test_sos_only_when_running(db_session, driver):
    trip = Trip(code="T-301", driver_id=driver.id)  # WHITE
    db_session.add(trip)
    db_session.commit()
    with pytest.raises(IncidentError):
        report_sos(db_session, trip, driver, IncidentKind.BREAKDOWN)


def test_resolve_unpauses(db_session, driver, supervisor):
    trip = _mk_green_trip(db_session, driver, supervisor)
    inc = report_sos(db_session, trip, driver, IncidentKind.BREAKDOWN, message="เครื่องดับ")
    resolve_incident(db_session, inc, supervisor, note="ซ่อมแล้ว วิ่งต่อได้")
    assert inc.status is IncidentStatus.RESOLVED
    assert trip.paused is False
    # วิ่งต่อได้จริง
    record_delivery(db_session, trip.drops[0], driver, 13.8, 100.6)
    assert trip.drops[0].delivered


def test_resolve_keeps_pause_when_other_open(db_session, driver, supervisor):
    trip = _mk_green_trip(db_session, driver, supervisor)
    inc1 = report_sos(db_session, trip, driver, IncidentKind.BREAKDOWN)
    inc2 = report_sos(db_session, trip, driver, IncidentKind.ACCIDENT)
    resolve_incident(db_session, inc1, supervisor)
    assert trip.paused is True   # ยังมี inc2 ค้าง
    resolve_incident(db_session, inc2, supervisor)
    assert trip.paused is False


def test_resolve_twice_rejected(db_session, driver, supervisor):
    trip = _mk_green_trip(db_session, driver, supervisor)
    inc = report_sos(db_session, trip, driver, IncidentKind.OTHER)
    resolve_incident(db_session, inc, supervisor)
    with pytest.raises(IncidentError):
        resolve_incident(db_session, inc, supervisor)
