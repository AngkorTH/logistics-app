"""Management services — User Management, Driver Rating, Monthly History, Vehicles

ทั้งหมดเป็นงานฝั่งบริหาร (Driver เข้าถึงไม่ได้ — บังคับสิทธิ์ที่ router)
"""
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models import Trip, User, Vehicle
from app.models.enums import Role, VehicleStatus
from app.services.audit import who_label, write_audit
from app.services.finance import compute_finance
from app.services.notification import push_notification


class ManageError(Exception):
    """คำสั่งจัดการที่ทำไม่ได้ (ข้อมูลชนกัน / ไม่พบเป้าหมาย ฯลฯ)"""


# --------------------------- User Management ---------------------------
def update_user(db: Session, target: User, actor: User, changes: dict) -> User:
    """แก้ข้อมูลส่วนตัวพนักงาน — เฉพาะ field ที่ส่งมา (None = ไม่แก้)"""
    applied = []
    for field in ("name", "phone", "role", "active", "notif"):
        if field in changes and changes[field] is not None:
            new_val = changes[field]
            if field == "phone":
                dup = db.query(User).filter(User.phone == new_val, User.id != target.id).first()
                if dup:
                    raise ManageError(f"เบอร์ {new_val} ถูกใช้โดยพนักงานคนอื่นแล้ว")
            setattr(target, field, new_val)
            applied.append(field)
    db.commit()
    db.refresh(target)
    write_audit(
        db, who_label(actor), "แก้ข้อมูลพนักงาน", target.emp_id,
        f"แก้ field: {', '.join(applied) or '—'}",
    )
    return target


def set_rating(db: Session, target: User, actor: User, rating: int) -> User:
    """ให้ดาวคนขับ 0-5 (Admin+) — ต้องเป็น Driver เท่านั้น"""
    if target.role is not Role.DRIVER:
        raise ManageError("ให้ดาวได้เฉพาะพนักงานขับรถเท่านั้น")
    if not 0 <= rating <= 5:
        raise ManageError("ดาวต้องอยู่ระหว่าง 0-5")
    target.rating = rating
    db.commit()
    db.refresh(target)
    write_audit(db, who_label(actor), "ให้คะแนนคนขับ", target.emp_id, f"{rating} ดาว")
    return target


# --------------------------- Monthly Trip History ---------------------------
def monthly_history(db: Session, driver: User) -> list[dict]:
    """สรุปประวัติทริปที่ปิดงานแล้วของคนขับ จัดกลุ่มรายเดือน (ใหม่→เก่า)"""
    trips = (
        db.query(Trip)
        .filter(Trip.driver_id == driver.id, Trip.closed_at.isnot(None))
        .all()
    )
    buckets: dict[str, dict] = defaultdict(
        lambda: {"trips": 0, "total_distance": 0.0, "total_allowance_net": 0.0, "total_penalty": 0.0}
    )
    for t in trips:
        key = t.closed_at.strftime("%Y-%m")
        fin = compute_finance(t)
        b = buckets[key]
        b["trips"] += 1
        b["total_distance"] += t.distance_km
        b["total_allowance_net"] += fin.allowance_net
        b["total_penalty"] += fin.penalty

    rows = [
        {
            "month": k,
            "trips": v["trips"],
            "total_distance": round(v["total_distance"], 2),
            "total_allowance_net": round(v["total_allowance_net"], 2),
            "total_penalty": round(v["total_penalty"], 2),
        }
        for k, v in buckets.items()
    ]
    rows.sort(key=lambda r: r["month"], reverse=True)
    return rows


def monthly_trip_rows(db: Session, driver: User, year: int, month: int) -> list[dict]:
    """ตารางทริปรายเที่ยวของคนขับในเดือน/ปีที่เลือก (flow: เลือกคนขับ → เลือกเดือน/ปี)

    ดึงเฉพาะทริปที่ปิดงานแล้วซึ่ง closed_at ตรงกับ year/month ที่ระบุ (ใหม่→เก่า)
    """
    trips = (
        db.query(Trip)
        .filter(Trip.driver_id == driver.id, Trip.closed_at.isnot(None))
        .order_by(Trip.closed_at.desc())
        .all()
    )
    rows = []
    for t in trips:
        if t.closed_at.year != year or t.closed_at.month != month:
            continue
        fin = compute_finance(t)
        rows.append({
            "trip_id": t.id,
            "code": t.code,
            "closed_at": t.closed_at.isoformat(),
            "plate": t.plate,
            "distance_km": t.distance_km,
            "difficulty": t.difficulty,
            "drops": len(t.drops),
            # งานย่อยเรียงตามลำดับ — หน้าประวัติกางดู "ต้นทาง → ปลายทาง" รายใบได้
            "sub_trips": [
                {
                    "seq": d.seq,
                    "origin": d.origin or "—",
                    "destination": d.destination or d.name,
                    "allowance": round(d.allowance, 2),
                    "delivered": d.delivered,
                    "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None,
                    "loaded_photo": d.loaded_photo,
                    "photo": d.photo,
                    "tarp": d.tarp,
                }
                for d in sorted(t.drops, key=lambda x: x.seq)
            ],
            "allowance_net": round(fin.allowance_net, 2),
            "penalty": round(fin.penalty, 2),
        })
    return rows


# --------------------------- Vehicle Assignment ---------------------------
def create_vehicle(db: Session, actor: User, plate: str, model: str, std_km_l: float) -> Vehicle:
    plate = plate.strip()
    if db.query(Vehicle).filter(Vehicle.plate == plate).first():
        raise ManageError(f"ทะเบียน {plate} มีอยู่แล้ว")
    v = Vehicle(plate=plate, model=model, std_km_l=std_km_l)
    db.add(v)
    db.commit()
    db.refresh(v)
    write_audit(db, who_label(actor), "เพิ่มทะเบียนรถ", plate, f"รุ่น {model}")
    return v


def update_vehicle(db: Session, vehicle: Vehicle, actor: User, changes: dict) -> Vehicle:
    for field in ("model", "std_km_l"):
        if field in changes and changes[field] is not None:
            setattr(vehicle, field, changes[field])
    db.commit()
    db.refresh(vehicle)
    write_audit(db, who_label(actor), "แก้ข้อมูลรถ", vehicle.plate, "")
    return vehicle


def set_vehicle_status(
    db: Session, vehicle: Vehicle, actor: User, new_status: VehicleStatus, reason: str
) -> Vehicle:
    """แอดมินสั่งรถเข้า/ออกจากการซ่อมด้วยมือ (สิทธิ์บังคับที่ router = require_admin)

    ต่างจาก flow เดิมที่รถเข้าซ่อมได้ทางเดียวคือ "คนขับแจ้งเหตุ" — อันนี้แอดมินกดเอง
    รถสถานะ MAINTENANCE จะถูกล็อกไม่ให้จ่ายงาน (เช็กอยู่แล้วใน assign endpoint)
    """
    if not reason or not reason.strip():
        raise ManageError("ต้องระบุเหตุผลการเปลี่ยนสถานะรถเสมอ")
    if vehicle.status is new_status:
        raise ManageError(f"รถ {vehicle.plate} อยู่ในสถานะนี้อยู่แล้ว")

    old = vehicle.status
    vehicle.status = new_status
    db.commit()
    db.refresh(vehicle)

    label = "แจ้งรถเข้าซ่อม" if new_status is VehicleStatus.MAINTENANCE else "ปลดล็อกรถกลับมาใช้งาน"
    write_audit(
        db, who_label(actor), label, vehicle.plate,
        f"{old.value} → {new_status.value} · เหตุผล: {reason.strip()}",
    )
    push_notification(
        db, "VEHICLE_STATUS",
        f"{label} · {vehicle.plate}",
        f"{who_label(actor)} เปลี่ยนสถานะรถเป็น {new_status.value} · เหตุผล: {reason.strip()}",
    )
    return vehicle


def assign_vehicle(db: Session, vehicle: Vehicle, actor: User, driver_id: int | None) -> Vehicle:
    """ผูก/ถอดคนขับประจำรถ — driver_id=None คือถอด"""
    if driver_id is not None:
        driver = db.get(User, driver_id)
        if not driver or driver.role is not Role.DRIVER:
            raise ManageError("driver_id ไม่ใช่พนักงานขับรถ")
        vehicle.driver_id = driver.id
        detail = f"ผูกคนขับ {driver.emp_id}"
    else:
        vehicle.driver_id = None
        detail = "ถอดคนขับประจำรถ"
    db.commit()
    db.refresh(vehicle)
    write_audit(db, who_label(actor), "ผูกทะเบียนรถ", vehicle.plate, detail)
    return vehicle
