"""Penalty (หลายรายการ) — บันทึกเงินหักแบบ line-item ผูก Trip + Driver

ต่อยอดจาก finance.apply_penalty (ยอดก้อนเดียว) → ที่นี่เก็บได้หลายบรรทัด
แต่ยังคงกฎเดิม: เหตุผลบังคับ · หักจากเบี้ยเลี้ยงรวมเท่านั้น (ห้ามทะลุ) · แจ้ง Admin
trip.penalty (ยอดรวม) จะถูก sync = ผลรวมของทุก line-item เพื่อให้ finance คิดถูก
"""
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.models import Penalty, Trip, User
from app.services.audit import who_label, write_audit
from app.services.finance import FinanceError


def deduction_leaderboard(db: Session, year: int | None, month: int | None) -> list[dict]:
    """จัดอันดับการหักเงินรายเดือน (task 3): group by คนขับ → ยอดรวม + จำนวนครั้ง

    เรียงจากคนที่ถูกหักเงินรวม "มากที่สุด" ลงมา (Sort Descending)
    กรองตามเดือน/ปีจาก Penalty.created_at (ถ้าไม่ส่งมา = ทั้งหมด)
    """
    q = (
        db.query(
            Penalty.driver_id,
            User.name,
            func.sum(Penalty.amount).label("total_amount"),
            func.count(Penalty.id).label("count"),
        )
        .join(User, Penalty.driver_id == User.id)
    )
    if year is not None:
        q = q.filter(extract("year", Penalty.created_at) == year)
    if month is not None:
        q = q.filter(extract("month", Penalty.created_at) == month)

    rows = q.group_by(Penalty.driver_id, User.name).order_by(func.sum(Penalty.amount).desc()).all()
    return [
        {
            "driver_id": driver_id,
            "driver_name": name,
            "total_amount": round(total or 0.0, 2),
            "count": int(cnt),
        }
        for driver_id, name, total, cnt in rows
    ]


def add_penalty(db: Session, trip: Trip, actor: User, amount: float, reason: str) -> Penalty:
    """เพิ่มรายการหักเงิน 1 บรรทัด

    การ์ด:
    - freeze แล้ว → ห้ามเพิ่ม (ต้องขอ correction)
    - reason ว่าง → FinanceError
    - amount <= 0 → FinanceError
    - ผลรวมหักทั้งหมด > เบี้ยเลี้ยงรวม+โบนัส → FinanceError (ห้ามทะลุค่าน้ำมัน/เงินเดือน)
    """
    if trip.frozen:
        raise FinanceError(f"ทริป {trip.code} ถูกล็อกการเงินแล้ว — เพิ่มรายการหักไม่ได้ ต้องขอปลดล็อก")
    if not reason or not reason.strip():
        raise FinanceError("ต้องระบุเหตุผลการหักเงินเสมอ")
    if amount <= 0:
        raise FinanceError("ยอดหักเงินต้องมากกว่า 0")

    existing = sum(p.amount for p in db.query(Penalty).filter(Penalty.trip_id == trip.id).all())
    allowance_total = round(sum(d.allowance for d in trip.drops), 2)
    ceiling = allowance_total + trip.bonus
    if round(existing + amount, 2) > ceiling:
        raise FinanceError(
            f"หักรวมได้ไม่เกินเบี้ยเลี้ยงรวมของทริป ({ceiling:.2f}) — "
            f"หักไปแล้ว {existing:.2f} · ห้ามหักเข้าค่าน้ำมันหรือเงินเดือน"
        )

    row = Penalty(
        trip_id=trip.id,
        driver_id=trip.driver_id,
        amount=round(float(amount), 2),
        reason=reason.strip(),
        created_by=actor.id,
        creator_name=who_label(actor),
    )
    db.add(row)
    db.flush()

    # sync ยอดรวมกลับไปที่ trip.penalty เพื่อให้ compute_finance คิดเบี้ยเลี้ยงสุทธิถูก
    trip.penalty = round(existing + row.amount, 2)
    trip.penalty_reason = row.reason
    db.commit()
    db.refresh(row)

    write_audit(
        db, who_label(actor), "หักเงิน", trip.code,
        f"หัก {row.amount:.2f} · เหตุผล: {row.reason} (รายการที่ {existing and '+' or ''}รวม {trip.penalty:.2f})",
    )
    _notify_admin(trip, actor, row)
    return row


def _notify_admin(trip: Trip, actor: User, row: Penalty) -> None:
    """แจ้ง Admin เมื่อมีการหักเงิน (stub — ต่อ push/inbox จริงภายหลัง)"""
    print(f"[NOTIFY→ADMIN] {who_label(actor)} หักเงินทริป {trip.code} {row.amount:.2f} บาท · {row.reason}")
