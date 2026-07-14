"""ทดสอบ schema ใหม่ (Phase 1): Inspection / Advance / Incident + Trip.paused"""
from app.models import (
    Advance,
    AdvanceStatus,
    Incident,
    IncidentKind,
    IncidentStatus,
    Inspection,
    InspectionStatus,
    Trip,
    User,
)


def _driver(db) -> User:
    return db.query(User).filter(User.emp_id == "D01").one()


def _trip(db, driver) -> Trip:
    trip = Trip(code="T-900", driver_id=driver.id)
    db.add(trip)
    db.commit()
    return trip


def test_trip_paused_defaults_false(db_session):
    trip = _trip(db_session, _driver(db_session))
    assert trip.paused is False


def test_inspection_roundtrip(db_session):
    drv = _driver(db_session)
    trip = _trip(db_session, drv)
    ins = Inspection(
        trip_id=trip.id, driver_id=drv.id,
        items='{"tires": true, "lights": false}',
        passed=False, defect_note="ไฟเลี้ยวซ้ายไม่ติด", defect_photo="/uploads/mock.jpg",
        status=InspectionStatus.PENDING_REVIEW,
    )
    db_session.add(ins)
    db_session.commit()

    got = db_session.query(Inspection).filter_by(trip_id=trip.id).one()
    assert got.status is InspectionStatus.PENDING_REVIEW
    assert got.defect_photo == "/uploads/mock.jpg"
    assert got.driver.emp_id == "D01"


def test_advance_roundtrip(db_session):
    drv = _driver(db_session)
    adv = Advance(code="A-01", driver_id=drv.id, amount=500, reason="ค่าน้ำมันสำรอง")
    db_session.add(adv)
    db_session.commit()

    got = db_session.query(Advance).filter_by(code="A-01").one()
    assert got.status is AdvanceStatus.PENDING
    assert got.trip_id is None          # ขอได้แม้ไม่มีทริปวิ่งอยู่
    assert got.deducted_trip_id is None  # ยังไม่ถูกหัก


def test_incident_roundtrip(db_session):
    drv = _driver(db_session)
    trip = _trip(db_session, drv)
    inc = Incident(
        code="S-01", trip_id=trip.id, driver_id=drv.id,
        kind=IncidentKind.ACCIDENT, message="ยางระเบิด", gps="13.75,100.50", photo="/uploads/sos.jpg",
    )
    trip.paused = True
    db_session.add(inc)
    db_session.commit()

    got = db_session.query(Incident).filter_by(code="S-01").one()
    assert got.status is IncidentStatus.OPEN
    assert got.trip.paused is True
