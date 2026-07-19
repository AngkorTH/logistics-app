"""สร้างข้อมูลตัวอย่าง (users/vehicles) เพื่อทดสอบ Login — รหัสผ่านเริ่มต้นทุกบัญชี: 1234

รัน: python -m app.seed
อ้างอิงชื่อ/รหัสจาก seed data ในไฟล์ prototype-ui — ทริปกระจายครบ 3 สี + Multi-Drop
+ บิล OCR Draft รอตรวจ + ทริปปิดงาน (frozen) พร้อมคำขอปลดล็อก PENDING
"""
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import Correction, Drop, Receipt, Role, Trip, User, Vehicle
from app.models.enums import CorrectionStatus, ReceiptKind, TripStatus
from app.security import hash_password

SEED_USERS = [
    ("D01", "สมชาย ใจดี", "0810000001", Role.DRIVER, True),
    ("D02", "ประเสริฐ มั่นคง", "0810000002", Role.DRIVER, True),
    ("D04", "อนุชา ตรงเวลา", "0810000004", Role.DRIVER, False),  # บัญชีถูกระงับ
    ("SV01", "ธนพล คุมงาน", "0820000001", Role.SUPERVISOR, True),
    ("AD01", "กมล ผู้จัดการ", "0830000001", Role.ADMIN, True),
    ("SA01", "ประธาน สูงสุด", "0840000001", Role.SUPER_ADMIN, True),
]

SEED_VEHICLES = [
    ("ผก-1234 กทม.", "Isuzu FRR 6W", 3.6, "D01"),
    ("บม-5678 นนทบุรี", "Hino 500 10W", 2.9, "D02"),
]


def run():
    db = SessionLocal()
    try:
        for emp_id, name, phone, role, active in SEED_USERS:
            if db.query(User).filter(User.emp_id == emp_id).first():
                continue
            db.add(User(
                emp_id=emp_id, name=name, phone=phone, role=role, active=active,
                password_hash=hash_password("1234"),
            ))
        db.commit()

        for plate, model, std, drv_emp in SEED_VEHICLES:
            if db.query(Vehicle).filter(Vehicle.plate == plate).first():
                continue
            drv = db.query(User).filter(User.emp_id == drv_emp).first()
            db.add(Vehicle(plate=plate, model=model, std_km_l=std, driver_id=drv.id if drv else None))
        db.commit()

        seed_trips(db)
        print(
            f"Seed เสร็จ: users={db.query(User).count()} vehicles={db.query(Vehicle).count()} "
            f"trips={db.query(Trip).count()} corrections={db.query(Correction).count()} (รหัสผ่าน: 1234)"
        )
    finally:
        db.close()


def seed_trips(db):
    """สร้างทริปตัวอย่างครบ 3 สี (idempotent — ข้ามถ้ามีทริปอยู่แล้ว)"""
    if db.query(Trip).count() > 0:
        return
    now = datetime.now(timezone.utc)
    d01 = db.query(User).filter(User.emp_id == "D01").first()
    d02 = db.query(User).filter(User.emp_id == "D02").first()
    sv = db.query(User).filter(User.emp_id == "SV01").first()

    # ---- T-001: GREEN Multi-Drop 3 จุด (จุด 1 ส่งแล้ว + บิล Draft รอ Supervisor ตรวจ) ----
    t1 = Trip(code="T-001", driver_id=d01.id, plate="ผก-1234 กทม.", status=TripStatus.GREEN,
              distance_km=120, assigned_at=now - timedelta(hours=1),
              finished_loading_at=now - timedelta(minutes=20))
    db.add(t1); db.flush()
    drops1 = [
        Drop(trip_id=t1.id, seq=1, name="ลำปาง → บางนา", origin="ลำปาง", destination="บจก. รุ่งเรือง (บางนา)", allowance=300, revenue=4285.71,
             delivered=True, photo="attached", tarp="attached", gps="13.66840,100.61000",
             delivered_at=now - timedelta(minutes=10)),
        Drop(trip_id=t1.id, seq=2, name="บางนา → พระราม 9", origin="บางนา", destination="เซ็นทรัล (พระราม 9)", allowance=350, revenue=5000.0),
        Drop(trip_id=t1.id, seq=3, name="พระราม 9 → ลาดพร้าว", origin="พระราม 9", destination="โลตัส (ลาดพร้าว)", allowance=300, revenue=4285.71),
    ]
    db.add_all(drops1); db.flush()
    # บิล OCR Draft (approved=False) — รอ Supervisor กดยืนยันใน Approval Center
    db.add_all([
        Receipt(drop_id=drops1[0].id, kind=ReceiptKind.FUEL, amount=1850, date="10 ก.ค. 69", approved=False),
        Receipt(drop_id=drops1[0].id, kind=ReceiptKind.TOLL, amount=240, date="10 ก.ค. 69", approved=False),
    ])

    # ---- T-002: ORANGE 2 จุด (จ่ายงานแล้ว กำลังไปขึ้นของ) ----
    t2 = Trip(code="T-002", driver_id=d02.id, plate="บม-5678 นนทบุรี", status=TripStatus.ORANGE,
              distance_km=95, assigned_at=now - timedelta(minutes=10))
    db.add(t2); db.flush()
    db.add_all([
        Drop(trip_id=t2.id, seq=1, name="นนทบุรี → สีลม", origin="นนทบุรี", destination="ไทยพาณิชย์ (สีลม)", allowance=400, revenue=5714.29),
        Drop(trip_id=t2.id, seq=2, name="สีลม → จรัญฯ", origin="สีลม", destination="แม็คโคร (จรัญ)", allowance=350, revenue=5000.0),
    ])

    # ---- T-003: WHITE รองาน (ยังไม่จ่ายงาน) ----
    t3 = Trip(code="T-003", driver_id=d01.id, status=TripStatus.WHITE, distance_km=0)
    db.add(t3); db.flush()
    db.add(Drop(trip_id=t3.id, seq=1, name="กรุงเทพ → รังสิต", origin="กรุงเทพ", destination="บิ๊กซี (รังสิต)", allowance=350, revenue=5000.0))

    # ---- H-100: ทริปปิดงานแล้ว (frozen) + คำขอปลดล็อกค่าน้ำมัน PENDING ----
    h = Trip(code="H-100", driver_id=d02.id, plate="บม-5678 นนทบุรี", status=TripStatus.WHITE,
             distance_km=95, frozen=True, frozen_fuel=980, frozen_toll=120,
             closed_at=now - timedelta(days=2), completed_at=now - timedelta(days=2),
             penalty=0, bonus=0)
    db.add(h); db.flush()
    hd = Drop(trip_id=h.id, seq=1, name="นนทบุรี → ศรีนครินทร์", origin="นนทบุรี", destination="ซีคอน (ศรีนครินทร์)", allowance=300, revenue=4285.71,
              delivered=True, photo="attached", tarp="attached", gps="13.64590,100.64690")
    db.add(hd); db.flush()
    db.add_all([
        Receipt(drop_id=hd.id, kind=ReceiptKind.FUEL, amount=980, approved=True),
        Receipt(drop_id=hd.id, kind=ReceiptKind.TOLL, amount=120, approved=True),
    ])
    db.add(Correction(
        code="C-01", trip_id=h.id, requested_by=sv.id, requester_name=f"{sv.name} ({sv.emp_id})",
        field_key="fuel", field_label="ค่าน้ำมัน", old_val=980, new_val=1180,
        reason="สลิปเบลอ คีย์ยอดผิด ตรวจสอบใหม่จากบิลจริง", status=CorrectionStatus.PENDING,
    ))
    db.commit()


if __name__ == "__main__":
    run()
