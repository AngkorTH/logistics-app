"""Smart Dispatch Queue — จัดลำดับคนขับเพื่อจ่ายงาน (skill.md ข้อ 6)

หน้าที่: ดึงคนขับ active ทั้งหมด แล้วจัดกลุ่มตามสถานะปัจจุบัน 3 สี
- WHITE  (รองาน)      : พร้อมรับงาน → เรียงตาม Priority
- ORANGE (ไปขึ้นของ)  : กำลังไปขึ้นของ (ติดงาน)
- GREEN  (ไปส่ง)      : กำลังส่งของ (ติดงาน)

สถานะปัจจุบันของคนขับ = สีของทริปที่ยัง "วิ่งอยู่" (ORANGE/GREEN ยังไม่ปิด)
ถ้าไม่มีทริปวิ่งอยู่เลย = WHITE (รองาน)

Priority การเรียงกลุ่ม WHITE (ผู้ใช้ยืนยันแล้ว):
  1. ความยากทริปก่อนหน้า: HARD ขึ้นก่อน (HARD → MEDIUM → EASY)
     — ชดเชยคนที่เพิ่งวิ่งงานหนักให้ได้คิวถัดไปเร็วขึ้น
  2. ความไวกดขนของขึ้นเสร็จของทริปก่อน (Orange→Green): น้อย = ไว = ขึ้นก่อน
  3. จำนวนดาว: มาก → น้อย
คนที่ไม่มีทริปก่อนหน้า (พนักงานใหม่) จะจัดไว้ท้ายกลุ่มในเกณฑ์ 1-2
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Trip, User
from app.models.enums import Role, TripDifficulty, TripStatus

# อันดับความยาก: HARD ขึ้นก่อน → ค่าน้อยมาก่อนเวลา sort ascending
_DIFFICULTY_RANK = {
    TripDifficulty.HARD: 0,
    TripDifficulty.MEDIUM: 1,
    TripDifficulty.EASY: 2,
}
_NO_PREV_RANK = 99  # คนไม่มีทริปก่อนหน้า → ท้ายสุดในเกณฑ์ความยาก


@dataclass
class DriverQueueItem:
    driver: User
    current_status: TripStatus
    prev_difficulty: TripDifficulty | None
    prev_load_seconds: float | None
    active_trip: Trip | None = None   # ทริปที่กำลังวิ่ง (ORANGE/GREEN) — เปิด Trip Details modal


def _active_trip(db: Session, driver: User) -> Trip | None:
    """ทริปที่ยังวิ่งอยู่ของคนขับ (ORANGE/GREEN) — None ถ้าว่าง (WHITE รองาน)

    ORANGE มาก่อน GREEN ถ้าบังเอิญมีหลายทริป (ปกติมีทริปวิ่งพร้อมกันได้ทีละ 1)
    """
    return (
        db.query(Trip)
        .filter(
            Trip.driver_id == driver.id,
            Trip.status.in_([TripStatus.ORANGE, TripStatus.GREEN]),
        )
        .order_by(Trip.assigned_at.desc())
        .first()
    )


def _previous_trip(db: Session, driver: User) -> Trip | None:
    """ทริปก่อนหน้าที่ปิดงานล่าสุดของคนขับ (ใช้ดึงความยาก + ความไวขึ้นของ)"""
    return (
        db.query(Trip)
        .filter(Trip.driver_id == driver.id, Trip.closed_at.isnot(None))
        .order_by(Trip.closed_at.desc())
        .first()
    )


def _load_seconds(trip: Trip | None) -> float | None:
    """ระยะเวลา Orange→Green ของทริป (วินาที) — วัดความไวกดขนของขึ้นเสร็จ"""
    if trip and trip.assigned_at and trip.finished_loading_at:
        return (trip.finished_loading_at - trip.assigned_at).total_seconds()
    return None


def _white_sort_key(item: DriverQueueItem):
    """คีย์เรียงกลุ่ม White ตาม Priority 3 ชั้น (tuple ascending)"""
    diff_rank = (
        _DIFFICULTY_RANK[item.prev_difficulty]
        if item.prev_difficulty is not None
        else _NO_PREV_RANK
    )
    # ความไว: ไม่มีข้อมูล = ท้ายสุด (inf) · ดาวมากก่อน = ใส่เครื่องหมายลบ
    load = item.prev_load_seconds if item.prev_load_seconds is not None else float("inf")
    return (diff_rank, load, -item.driver.rating)


def build_dispatch_queue(db: Session) -> dict[str, list[DriverQueueItem]]:
    """สร้างคิวจ่ายงานจัดกลุ่ม 3 สี — กลุ่ม White เรียงลำดับตาม Priority เรียบร้อย"""
    drivers = (
        db.query(User)
        .filter(User.role == Role.DRIVER, User.active.is_(True))
        .all()
    )

    groups: dict[str, list[DriverQueueItem]] = {"white": [], "orange": [], "green": []}
    for drv in drivers:
        active = _active_trip(db, drv)
        status = active.status if active else TripStatus.WHITE
        prev = _previous_trip(db, drv)
        item = DriverQueueItem(
            driver=drv,
            current_status=status,
            prev_difficulty=prev.difficulty if prev else None,
            prev_load_seconds=_load_seconds(prev),
            active_trip=active,
        )
        if status is TripStatus.ORANGE:
            groups["orange"].append(item)
        elif status is TripStatus.GREEN:
            groups["green"].append(item)
        else:
            groups["white"].append(item)

    groups["white"].sort(key=_white_sort_key)
    return groups
