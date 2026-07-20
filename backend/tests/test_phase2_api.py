"""Integration tests: endpoint ใหม่ Phase 2
- จ่ายงาน auto-plate (ข้อ 2.1): ไม่ผูกรถ → 400 / ผูกแล้วดึงทะเบียนเอง
- แท็บ 'รอตรวจ' (ข้อ 2.2): เรียงเก่า→ใหม่ + ยืนยันแล้วหายจากคิว
- Advance API ครบวงจร + RBAC
- Audit filter who/month/year (ประวัติการแก้ ข้อ 3.1)
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Drop, Role, Trip, User, Vehicle
from app.models.enums import TripStatus
from app.security import hash_password
from tests.conftest import PHOTO, ODO_PHOTO


def login(client, ident, pw="1234"):
    r = client.post("/auth/login", json={"identifier": ident, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def seeded(db_session):
    db = db_session
    db.add_all([
        User(emp_id="SV01", name="ธนพล คุมงาน", phone="0820000001",
             role=Role.SUPERVISOR, active=True, password_hash=hash_password("1234")),
    ])
    db.commit()
    d01 = db.query(User).filter(User.emp_id == "D01").first()
    db.add(Vehicle(plate="70-1122", model="Hino 500", driver_id=d01.id))
    trip = Trip(code="T-500", driver_id=d01.id, status=TripStatus.WHITE)
    db.add(trip)
    db.commit()
    db.add(Drop(origin="ต้นทาง", destination="ปลายทาง", trip_id=trip.id, seq=1, name="จุด A", allowance=400))
    db.commit()
    return {"trip_id": trip.id, "driver_id": d01.id}


@pytest.fixture()
def client():
    return TestClient(app)


def _run_to_done(client, sv, drv, tid):
    """จ่ายงาน → ตรวจรถ → เขียว → ส่งงานย่อยครบ → Supervisor กด 'จบเที่ยว' (รอล็อกการเงิน)"""
    assert client.post(f"/trips/{tid}/assign", json={}, headers=sv).status_code == 200
    r = client.post(f"/trips/{tid}/inspection",
                    json={"items": {"tires": True},
                          "odometer_start": 1000, "odometer_photo_b64": ODO_PHOTO}, headers=drv)
    assert r.status_code == 200
    assert client.post(f"/trips/{tid}/finish-loading",
                       json={"lat": 13.7, "lng": 100.5, "odometer_start": 1000, "odometer_photo_b64": ODO_PHOTO, "loaded_photo_b64": ODO_PHOTO}, headers=drv).status_code == 200
    trip = client.get(f"/trips/{tid}", headers=sv).json()
    for d in trip["drops"]:
        assert client.post(f"/drops/{d['id']}/delivery",
                           json={"lat": 13.8, "lng": 100.6, "photo_b64": ODO_PHOTO}, headers=drv).status_code == 200
    assert client.post(f"/trips/{tid}/complete", json={}, headers=sv).status_code == 200


def test_assign_requires_bound_vehicle(client, seeded, db_session):
    """คนขับไม่มีรถผูก → จ่ายงานโดน 400 พร้อมข้อความชี้ไปหน้า 'คลังรถยนต์'"""
    sv = login(client, "SV01")
    v = db_session.query(Vehicle).filter_by(driver_id=seeded["driver_id"]).one()
    v.driver_id = None
    db_session.commit()
    r = client.post(f"/trips/{seeded['trip_id']}/assign", json={}, headers=sv)
    assert r.status_code == 400
    assert "คลังรถยนต์" in r.json()["detail"]


def test_assign_pulls_plate_automatically(client, seeded):
    sv = login(client, "SV01")
    r = client.post(f"/trips/{seeded['trip_id']}/assign", json={}, headers=sv)
    assert r.status_code == 200
    assert r.json()["plate"] == "70-1122"


def test_pending_review_queue(client, seeded):
    """ทริปจบงานเข้าคิวรอตรวจ → กดยืนยัน (close) → หายจากคิว (เข้าประวัติ)"""
    sv, drv = login(client, "SV01"), login(client, "D01")
    tid = seeded["trip_id"]
    _run_to_done(client, sv, drv, tid)

    q = client.get("/trips/pending-review", headers=sv).json()
    assert [t["id"] for t in q] == [tid]

    # Driver เข้าแท็บรอตรวจไม่ได้
    assert client.get("/trips/pending-review", headers=drv).status_code == 403

    # ยืนยันความถูกต้อง = ล็อกการเงิน → ออกจากคิว
    assert client.post(f"/trips/{tid}/close", headers=sv).status_code == 200
    assert client.get("/trips/pending-review", headers=sv).json() == []


def test_advance_api_flow(client, seeded):
    """คนขับขอเบิก → supervisor อนุมัติ → ปิดทริปแล้วยอดถูกหักใน payout"""
    sv, drv = login(client, "SV01"), login(client, "D01")
    tid = seeded["trip_id"]

    # supervisor ยื่นขอเบิกเองไม่ได้ (ปุ่มของคนขับ)
    assert client.post("/advances", json={"amount": 100, "reason": "x"},
                       headers=sv).status_code == 403

    _run_to_done(client, sv, drv, tid)
    r = client.post("/advances", json={"amount": 150, "reason": "ค่าน้ำมันสำรอง"}, headers=drv)
    assert r.status_code == 200
    aid = r.json()["id"]

    # driver อนุมัติเองไม่ได้
    assert client.post(f"/advances/{aid}/approve", headers=drv).status_code == 403
    assert client.post(f"/advances/{aid}/approve", headers=sv).status_code == 200

    assert client.post(f"/trips/{tid}/close", headers=sv).status_code == 200
    fin = client.get(f"/trips/{tid}", headers=sv).json()["finance"]
    assert fin["advance_total"] == 150
    assert fin["payout_net"] == 400 - 150  # เบี้ยเลี้ยง 400 ไม่มีบิล


def test_audit_filters(client, seeded, db_session):
    """ประวัติการแก้ (Admin+): กรอง who + ปี/เดือน ได้ · Supervisor เข้าไม่ได้"""
    sv, drv = login(client, "SV01"), login(client, "D01")
    ad = login(client, "AD01")
    _run_to_done(client, sv, drv, seeded["trip_id"])

    assert client.get("/audit-logs", headers=sv).status_code == 403

    logs = client.get("/audit-logs", params={"who": "ธนพล"}, headers=ad).json()
    assert logs and all("ธนพล" in x["who"] for x in logs)

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    assert client.get("/audit-logs", params={"year": now.year, "month": now.month},
                      headers=ad).json()
    assert client.get("/audit-logs", params={"year": now.year + 1}, headers=ad).json() == []
