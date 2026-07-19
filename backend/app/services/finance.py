"""Financial Operations & Penalty — คำนวณเบี้ยเลี้ยง/หักเงิน (skill.md ข้อ 3)

หลักการหักเงินที่ห้ามพลาด:
- หักจาก **"เบี้ยเลี้ยงรวมของทริป"** เท่านั้น (ผลรวม allowance ของทุกจุด + bonus)
  ห้ามหักเข้าเนื้อค่าน้ำมัน/ทางหลวง หรือเงินเดือน
- Supervisor ต้อง **"พิมพ์เหตุผลเสมอ"** ถึงจะหักได้ (บังคับ)
- หักได้ไม่เกินเบี้ยเลี้ยงรวม (ยอดสุทธิเบี้ยเลี้ยงไม่ติดลบ) — เกินให้เตือน/บล็อก
- หักเงินแล้วต้องแจ้ง Admin (stub notify)

ยอดน้ำมัน/ทางหลวงคิดจาก Receipt ที่ **approved แล้วเท่านั้น** (draft OCR ไม่นับ)
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session, object_session

from app.models import Receipt, Trip
from app.models.enums import ReceiptKind
from app.services.audit import who_label, write_audit


class FinanceError(Exception):
    """ธุรกรรมการเงินที่ทำไม่ได้ (freeze แล้ว / ไม่มีเหตุผล / หักเกินเบี้ยเลี้ยง)"""


@dataclass
class TripFinance:
    """สรุปการเงินของทริป — คิดสด ไม่เก็บลง DB (ยกเว้นตอน freeze)"""
    allowance_total: float   # ผลรวมเบี้ยเลี้ยงทุกจุด
    bonus: float             # โบนัสระดับทริป
    penalty: float           # ยอดหัก (หักจากเบี้ยเลี้ยง+โบนัส)
    allowance_net: float     # เบี้ยเลี้ยงสุทธิหลังหัก (ไม่ต่ำกว่า 0)
    fuel_total: float        # ค่าน้ำมันจากบิล approved
    toll_total: float        # ค่าทางหลวงจากบิล approved
    advance_total: float     # ยอดเบิกล่วงหน้าที่หัก/รอหักกับทริปนี้
    payout_net: float        # ยอดจ่ายสุทธิ = fuel + toll + allowance_net − advance


def trip_receipts(trip: Trip):
    """บิลทั้งหมดของทริป = บิลรายจุดส่ง + บิลที่ผูกทริปตรงๆ (แจ้งเติมน้ำมันระหว่างทาง)"""
    for drop in trip.drops:
        yield from drop.receipts
    yield from trip.trip_receipts


def _approved_sum(trip: Trip, kind: ReceiptKind) -> float:
    """รวมยอดบิลชนิดหนึ่งของทริป เฉพาะที่ approved แล้ว"""
    total = sum(r.amount for r in trip_receipts(trip) if r.kind is kind and r.approved)
    return round(total, 2)


def total_liters(trip: Trip) -> float:
    """ลิตรรวมที่เติมทั้งทริป — นับทุกบิลน้ำมันที่มีจำนวนลิตร (ไม่ต้องรออนุมัติยอดเงิน)"""
    total = sum(
        r.liters or 0.0 for r in trip_receipts(trip) if r.kind is ReceiptKind.FUEL
    )
    return round(total, 2)


def compute_finance(trip: Trip) -> TripFinance:
    """คำนวณสรุปการเงินของทริป (ถ้า freeze แล้วใช้ยอดที่แช่ไว้เป็นแหล่งความจริงของน้ำมัน/ทางหลวง)"""
    allowance_total = round(sum(d.allowance for d in trip.drops), 2)
    base = allowance_total + trip.bonus
    allowance_net = round(max(base - trip.penalty, 0.0), 2)

    if trip.frozen and trip.frozen_fuel is not None:
        fuel_total = trip.frozen_fuel
        toll_total = trip.frozen_toll or 0.0
    else:
        fuel_total = _approved_sum(trip, ReceiptKind.FUEL)
        toll_total = _approved_sum(trip, ReceiptKind.TOLL)

    # ยอดเบิกล่วงหน้า: หลังล็อกการเงิน = ยอดที่ประทับหักกับทริปนี้ (snapshot ถาวร)
    # ก่อนล็อก = พรีวิวยอด APPROVED ที่ยังไม่ถูกหักของคนขับ (จะถูกหักตอน close_trip)
    # import ในฟังก์ชันเพื่อเลี่ยง circular import (advance พึ่ง audit/notification เท่านั้น)
    from app.services.advance import deducted_advance_total, undeducted_advance_total

    db = object_session(trip)
    if db is None:
        advance_total = 0.0
    elif trip.frozen:
        advance_total = deducted_advance_total(db, trip.id)
    else:
        advance_total = undeducted_advance_total(db, trip.driver_id)

    payout_net = round(fuel_total + toll_total + allowance_net - advance_total, 2)

    return TripFinance(
        allowance_total=allowance_total,
        bonus=trip.bonus,
        penalty=trip.penalty,
        allowance_net=allowance_net,
        fuel_total=fuel_total,
        toll_total=toll_total,
        advance_total=advance_total,
        payout_net=payout_net,
    )


def apply_penalty(db: Session, trip: Trip, actor, amount: float, reason: str) -> Trip:
    """ตั้งยอดหักเงินของทริป — บังคับใส่เหตุผล และหักจากเบี้ยเลี้ยงรวมเท่านั้น

    การ์ด:
    - freeze แล้ว → ห้ามแก้ (ต้องขอ correction)
    - reason ว่าง → FinanceError (พิมพ์เหตุผลเสมอ)
    - amount ติดลบ → FinanceError
    - amount > เบี้ยเลี้ยงรวม+โบนัส → FinanceError (ห้ามหักทะลุเข้าค่าน้ำมัน/เงินเดือน)
    """
    if trip.frozen:
        raise FinanceError(f"ทริป {trip.code} ถูกล็อกการเงินแล้ว — แก้ยอดหักไม่ได้ ต้องขอปลดล็อก")
    if not reason or not reason.strip():
        raise FinanceError("ต้องระบุเหตุผลการหักเงินเสมอ")
    if amount < 0:
        raise FinanceError("ยอดหักเงินติดลบไม่ได้")

    allowance_total = round(sum(d.allowance for d in trip.drops), 2)
    ceiling = allowance_total + trip.bonus
    if amount > ceiling:
        raise FinanceError(
            f"หักได้ไม่เกินเบี้ยเลี้ยงรวมของทริป ({ceiling:.2f}) — "
            f"ห้ามหักเข้าเนื้อค่าน้ำมันหรือเงินเดือน"
        )

    trip.penalty = round(float(amount), 2)
    trip.penalty_reason = reason.strip()
    db.commit()
    db.refresh(trip)

    write_audit(
        db, who_label(actor), "หักเงิน", trip.code,
        f"หัก {trip.penalty:.2f} จากเบี้ยเลี้ยงรวม · เหตุผล: {trip.penalty_reason}",
    )
    _notify_admin(trip, actor)
    return trip


def set_bonus(db: Session, trip: Trip, actor, amount: float) -> Trip:
    """ตั้งโบนัส/เบี้ยเลี้ยงพิเศษระดับทริป (freeze แล้วห้ามแก้)"""
    if trip.frozen:
        raise FinanceError(f"ทริป {trip.code} ถูกล็อกการเงินแล้ว — แก้โบนัสไม่ได้")
    if amount < 0:
        raise FinanceError("โบนัสติดลบไม่ได้")
    trip.bonus = round(float(amount), 2)
    db.commit()
    db.refresh(trip)
    write_audit(db, who_label(actor), "ตั้งโบนัส", trip.code, f"โบนัส {trip.bonus:.2f}")
    return trip


def _notify_admin(trip: Trip, actor) -> None:
    """แจ้งเตือน Admin เมื่อมีการหักเงิน (stub — จะต่อ push/inbox จริงภายหลัง)"""
    print(f"[NOTIFY→ADMIN] {who_label(actor)} หักเงินทริป {trip.code} {trip.penalty:.2f} บาท")


def trip_summary(trip: Trip) -> dict:
    """สรุปรวบยอดทั้งเที่ยว (ใช้ตอนกด "จบเที่ยว" และในประวัติทริป)

    - legs        = จำนวนขาที่วิ่งทั้งหมด (งานย่อยที่ส่งสำเร็จแล้ว) / legs_total = ที่จ่ายไปทั้งหมด
    - fuel_liters = ลิตรรวมทุกบิลน้ำมันในเที่ยว · fuel_cost = ยอดเงินค่าน้ำมันที่อนุมัติแล้ว
    - odometer    = เลขไมล์ต้นเที่ยว → ปลายเที่ยว · total_km = ระยะทางรวมทั้งเที่ยว
    - route       = รายการเส้นทางเรียงลำดับ เช่น 1. ลำปาง ไป กรุงเทพฯ
    """
    fin = compute_finance(trip)
    drops = sorted(trip.drops, key=lambda d: d.seq)

    if trip.odometer_start is not None and trip.odometer_end is not None:
        total_km = round(trip.odometer_end - trip.odometer_start, 2)
    else:
        total_km = round(trip.distance_km or 0.0, 2)

    return {
        "legs": sum(1 for d in drops if d.delivered),
        "legs_total": len(drops),
        "fuel_liters": total_liters(trip),
        "fuel_cost": fin.fuel_total,
        "toll_cost": fin.toll_total,
        "odometer_start": trip.odometer_start,
        "odometer_end": trip.odometer_end,
        "total_km": total_km,
        "km_per_liter": trip.km_per_liter,
        "route": [
            {
                "seq": d.seq,
                "origin": d.origin or "—",
                "destination": d.destination or d.name,
                "delivered": d.delivered,
                "allowance": round(d.allowance, 2),
            }
            for d in drops
        ],
    }
