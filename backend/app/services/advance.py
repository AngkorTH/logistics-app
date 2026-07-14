"""Advance Payment — เบิกเงินล่วงหน้าของคนขับ (ข้อ 1.3)

Flow:
- คนขับขอเบิก: ระบุยอด + เหตุผล (บังคับ) → PENDING + แจ้งเตือนทีมคุมงาน
- คุมงาน/แอดมิน/ซุปเปอร์แอดมินอนุมัติหรือปฏิเสธ
- ยอด APPROVED ที่ยังไม่ถูกหัก จะถูกหักอัตโนมัติตอน "ล็อกการเงิน" (close_trip)
  โดยประทับ deducted_trip_id/deducted_at กันหักซ้ำ — หักจากยอดจ่ายสุทธิของทริป
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Advance, Trip, User
from app.models.enums import AdvanceStatus, TripStatus
from app.services.audit import who_label, write_audit
from app.services.notification import push_notification


class AdvanceError(Exception):
    """คำขอเบิกเงินที่ทำไม่ได้ (ยอดผิด / ไม่มีเหตุผล / สถานะผิดจังหวะ)"""


def request_advance(db: Session, driver: User, amount: float, reason: str) -> Advance:
    """คนขับยื่นขอเบิกเงินล่วงหน้า — ผูกกับทริปที่กำลังวิ่งอยู่ถ้ามี"""
    if amount <= 0:
        raise AdvanceError("ยอดเบิกต้องมากกว่า 0")
    if not reason or not reason.strip():
        raise AdvanceError("ต้องระบุเหตุผลการเบิกเงินเสมอ")

    active = (
        db.query(Trip)
        .filter(
            Trip.driver_id == driver.id,
            Trip.status.in_([TripStatus.ORANGE, TripStatus.GREEN]),
        )
        .order_by(Trip.assigned_at.desc())
        .first()
    )
    code = f"A-{db.query(Advance).count() + 1:02d}"
    adv = Advance(
        code=code,
        driver_id=driver.id,
        trip_id=active.id if active else None,
        amount=round(float(amount), 2),
        reason=reason.strip(),
    )
    db.add(adv)
    db.commit()
    db.refresh(adv)

    write_audit(
        db, who_label(driver), "ขอเบิกเงินล่วงหน้า", adv.code,
        f"ยอด {adv.amount:.2f} · เหตุผล: {adv.reason}"
        + (f" · ทริป {active.code}" if active else ""),
    )
    push_notification(
        db, "ADVANCE_REQUEST", f"ขอเบิกเงินล่วงหน้า {adv.amount:.2f} บาท",
        f"{who_label(driver)} · เหตุผล: {adv.reason}",
        active.id if active else None,
    )
    return adv


def decide_advance(db: Session, adv: Advance, actor: User, approve: bool) -> Advance:
    """คุมงาน/แอดมินอนุมัติหรือปฏิเสธคำขอเบิก (ตัดสินได้ครั้งเดียว)"""
    if adv.status is not AdvanceStatus.PENDING:
        raise AdvanceError(f"คำขอ {adv.code} อยู่สถานะ {adv.status.value} — ตัดสินซ้ำไม่ได้")

    adv.status = AdvanceStatus.APPROVED if approve else AdvanceStatus.REJECTED
    adv.decided_by = actor.id
    adv.decider_name = who_label(actor)
    adv.decided_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(adv)

    write_audit(
        db, who_label(actor),
        "อนุมัติเบิกเงินล่วงหน้า" if approve else "ปฏิเสธเบิกเงินล่วงหน้า",
        adv.code, f"ยอด {adv.amount:.2f} ของ {adv.driver.name}",
    )
    return adv


def undeducted_advance_total(db: Session, driver_id: int) -> float:
    """ยอดเบิกที่อนุมัติแล้วแต่ยังไม่ถูกหัก — ใช้พรีวิวยอดจ่ายสุทธิก่อนปิดทริป"""
    advs = (
        db.query(Advance)
        .filter(
            Advance.driver_id == driver_id,
            Advance.status == AdvanceStatus.APPROVED,
            Advance.deducted_at.is_(None),
        )
        .all()
    )
    return round(sum(a.amount for a in advs), 2)


def deducted_advance_total(db: Session, trip_id: int) -> float:
    """ยอดเบิกที่ถูกหักไปแล้วกับทริปนี้ (snapshot ถาวรหลังล็อกการเงิน)"""
    advs = db.query(Advance).filter(Advance.deducted_trip_id == trip_id).all()
    return round(sum(a.amount for a in advs), 2)


def deduct_advances_on_close(db: Session, trip: Trip) -> float:
    """หักยอดเบิกล่วงหน้าที่อนุมัติแล้วทั้งหมดของคนขับเข้าทริปนี้ (เรียกจาก close_trip)

    ประทับ deducted_trip_id + deducted_at กันหักซ้ำ — ผู้เรียกเป็นคน commit
    """
    advs = (
        db.query(Advance)
        .filter(
            Advance.driver_id == trip.driver_id,
            Advance.status == AdvanceStatus.APPROVED,
            Advance.deducted_at.is_(None),
        )
        .all()
    )
    now = datetime.now(timezone.utc)
    total = 0.0
    for a in advs:
        a.deducted_trip_id = trip.id
        a.deducted_at = now
        total += a.amount
    return round(total, 2)
