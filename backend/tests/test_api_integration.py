"""Integration tests: API Router ครบวงจร Evidence / Finance / Correction

ยืนยันว่า endpoint รันได้จริง + Auth-Guard (require_role) + Ownership check ทำงานถูก
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Drop, Role, Trip, User, Vehicle
from app.models.enums import ReceiptKind, TripStatus
from app.security import hash_password
from tests.conftest import ODO_PHOTO


def login(client, ident, pw="1234"):
    r = client.post("/auth/login", json={"identifier": ident, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def seeded(db_session):
    """เพิ่ม supervisor, super_admin, driver คนที่สอง + ทริปของ D01 (2 จุด)"""
    db = db_session
    db.add_all([
        User(emp_id="SV01", name="ธนพล คุมงาน", phone="0820000001",
             role=Role.SUPERVISOR, active=True, password_hash=hash_password("1234")),
        User(emp_id="SA01", name="ใหญ่ สุดยอด", phone="0840000001",
             role=Role.SUPER_ADMIN, active=True, password_hash=hash_password("1234")),
        User(emp_id="D02", name="สมหญิง", phone="0810000002",
             role=Role.DRIVER, active=True, password_hash=hash_password("1234")),
    ])
    db.commit()
    d01 = db.query(User).filter(User.emp_id == "D01").first()
    # ผูกรถให้ D01 — จ่ายงานดึงทะเบียนอัตโนมัติจากคลังรถ (ข้อ 2.1)
    db.add(Vehicle(plate="1กก-1234", model="Isuzu FTR", driver_id=d01.id))
    trip = Trip(code="T-100", driver_id=d01.id, status=TripStatus.WHITE, distance_km=120)
    db.add(trip)
    db.commit()
    db.refresh(trip)
    db.add_all([
        Drop(trip_id=trip.id, seq=1, name="จุด A", allowance=300),
        Drop(trip_id=trip.id, seq=2, name="จุด B", allowance=200),
    ])
    db.commit()
    db.refresh(trip)
    return {"trip_id": trip.id, "drop_ids": [d.id for d in trip.drops]}


@pytest.fixture()
def client():
    return TestClient(app)


# --------------------------- Auth-Guard ---------------------------
def test_requires_token(client, seeded):
    assert client.get(f"/trips/{seeded['trip_id']}").status_code == 401


def test_driver_cannot_assign(client, seeded):
    """จ่ายงานเป็นสิทธิ์ Supervisor+ — Driver โดน 403"""
    h = login(client, "D01")
    r = client.post(f"/trips/{seeded['trip_id']}/assign", json={}, headers=h)
    assert r.status_code == 403


def test_only_super_admin_approves_correction(client, seeded, db_session):
    """freeze ทริปก่อน แล้วขอ correction — supervisor อนุมัติเองไม่ได้ (ต้อง Super Admin)"""
    tid = seeded["trip_id"]
    # ไล่สถานะจนปิดงาน freeze
    trip = db_session.get(Trip, tid)
    trip.status = TripStatus.GREEN
    for d in trip.drops:
        d.photo = "attached"
    db_session.commit()
    sv = login(client, "SV01")
    # จบเที่ยว (force เพราะยังไม่ได้ mark delivered) แล้วจึงล็อกการเงิน
    assert client.post(f"/trips/{tid}/complete", json={"force": True}, headers=sv).status_code == 200
    assert client.post(f"/trips/{tid}/close", headers=sv).status_code == 200
    # ขอปลดล็อก
    r = client.post(f"/trips/{tid}/corrections",
                    json={"field_key": "bonus", "new_val": 500, "reason": "แก้โบนัส"}, headers=sv)
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    # supervisor อนุมัติเอง → 403
    assert client.post(f"/corrections/{cid}/approve", headers=sv).status_code == 403
    # super admin อนุมัติ → 200
    sa = login(client, "SA01")
    ra = client.post(f"/corrections/{cid}/approve", headers=sa)
    assert ra.status_code == 200, ra.text
    assert ra.json()["status"] == "APPROVED"
    assert db_session.get(Trip, tid).bonus == 500


# --------------------------- Ownership ---------------------------
def test_driver_cannot_view_others_trip(client, seeded):
    """D02 ดูทริปของ D01 ไม่ได้ (403)"""
    h = login(client, "D02")
    assert client.get(f"/trips/{seeded['trip_id']}", headers=h).status_code == 403


def test_driver_only_sees_own_in_list(client, seeded):
    h = login(client, "D02")
    r = client.get("/trips", headers=h)
    assert r.status_code == 200
    assert r.json() == []  # D02 ไม่มีทริป


def test_driver_cannot_upload_to_others_drop(client, seeded):
    h = login(client, "D02")
    r = client.post(f"/drops/{seeded['drop_ids'][0]}/tarp", headers=h)
    assert r.status_code == 403


# --------------------------- Happy path ครบวงจร ---------------------------
def test_full_flow(client, seeded, db_session):
    tid = seeded["trip_id"]
    d0, d1 = seeded["drop_ids"]
    sv = login(client, "SV01")
    drv = login(client, "D01")

    # จ่ายงาน → ORANGE
    r = client.post(f"/trips/{tid}/assign", json={}, headers=sv)
    assert r.status_code == 200 and r.json()["status"] == "ORANGE"
    assert r.json()["plate"] == "1กก-1234"  # ดึงจากคลังรถอัตโนมัติ

    # ยังไม่ตรวจสภาพรถ → กดขนของขึ้นเสร็จไม่ได้ (hard-block ด่านตรวจรถ)
    r = client.post(f"/trips/{tid}/finish-loading", json={"lat": 13.7, "lng": 100.5, "odometer_start": 1000, "odometer_photo_b64": ODO_PHOTO}, headers=drv)
    assert r.status_code == 400

    # คนขับส่งผลตรวจสภาพรถผ่านทุกข้อ → PASSED
    r = client.post(f"/trips/{tid}/inspection",
                    json={"items": {"tires": True, "lights": True, "tarp": True},
                          "odometer_start": 1000, "odometer_photo_b64": ODO_PHOTO}, headers=drv)
    assert r.status_code == 200 and r.json()["status"] == "PASSED"

    # คนขับขนของขึ้นเสร็จ → GREEN
    r = client.post(f"/trips/{tid}/finish-loading", json={"lat": 13.7, "lng": 100.5, "odometer_start": 1000, "odometer_photo_b64": ODO_PHOTO}, headers=drv)
    assert r.status_code == 200 and r.json()["status"] == "GREEN"

    # อัปบิลน้ำมันจุดแรก (OCR draft)
    r = client.post(f"/drops/{d0}/receipt",
                    json={"kind": "FUEL", "ocr_amount": 800}, headers=drv)
    assert r.status_code == 200 and r.json()["approved"] is False
    rid = r.json()["id"]

    # ยังไม่ approve → finance fuel = 0
    fin = client.get(f"/trips/{tid}/finance", headers=sv).json()
    assert fin["fuel_total"] == 0

    # supervisor อนุมัติบิล → fuel_total = 800
    assert client.post(f"/receipts/{rid}/approve", json={}, headers=sv).status_code == 200
    fin = client.get(f"/trips/{tid}/finance", headers=sv).json()
    assert fin["fuel_total"] == 800

    # หักเงินต้องมีเหตุผล — ไม่มีเหตุผล → 422 (schema) ; มีเหตุผล → หักจากเบี้ยเลี้ยง
    assert client.post(f"/trips/{tid}/penalty", json={"amount": 100, "reason": ""}, headers=sv).status_code == 422
    r = client.post(f"/trips/{tid}/penalty", json={"amount": 100, "reason": "ส่งช้า"}, headers=sv)
    assert r.status_code == 200
    assert r.json()["allowance_net"] == 400  # 500 - 100

    # หักเกินเบี้ยเลี้ยงรวม → 400
    assert client.post(f"/trips/{tid}/penalty",
                       json={"amount": 9999, "reason": "เยอะ"}, headers=sv).status_code == 400

    # ส่งของครบ 2 จุด
    for d in (d0, d1):
        r = client.post(f"/drops/{d}/delivery", json={"lat": 13.8, "lng": 100.6}, headers=drv)
        assert r.status_code == 200 and r.json()["delivered"] is True

    # Supervisor กด 'จบเที่ยว' ก่อน แล้วค่อยล็อกการเงิน → WHITE + freeze
    assert client.post(f"/trips/{tid}/complete", json={}, headers=sv).status_code == 200
    r = client.post(f"/trips/{tid}/close", headers=sv)
    assert r.status_code == 200 and r.json()["status"] == "WHITE"
    assert r.json()["frozen"] is True

    # freeze แล้ว หักเงินซ้ำไม่ได้ → 400
    assert client.post(f"/trips/{tid}/penalty",
                       json={"amount": 50, "reason": "x"}, headers=sv).status_code == 400


def test_assign_skip_order_warns_409(client, seeded):
    """จ่ายงานทริปที่ไม่ได้อยู่ WHITE → 409 (warn-don't-block) แล้ว force ผ่าน"""
    tid = seeded["trip_id"]
    sv = login(client, "SV01")
    assert client.post(f"/trips/{tid}/assign", json={}, headers=sv).status_code == 200
    # ตอนนี้ ORANGE — จ่ายซ้ำ → 409
    r = client.post(f"/trips/{tid}/assign", json={}, headers=sv)
    assert r.status_code == 409
    # force
    r = client.post(f"/trips/{tid}/assign", json={"force": True}, headers=sv)
    assert r.status_code == 200
