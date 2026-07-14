"""Trip Adjustment — แก้ข้อมูลทริปแบบรวม พร้อมบังคับบันทึกเหตุผล (claude.md ข้อ 6.5)

Admin และ Supervisor แก้ได้ (RBAC ที่ router = require_supervisor)
กติกาสำคัญ:
- ทริปที่ freeze แล้ว ห้ามแก้ผ่านช่องนี้ (ต้องขอ Correction)
- แก้ penalty ต้องแนบเหตุผลของการหักเงินด้วย และห้ามหักเกินเบี้ยเลี้ยงรวม+โบนัส
- ทุกการแก้ไขเขียน Audit Trail 1 บรรทัด ระบุ edit_reason + สรุป field ที่แก้
"""
from app.models import Trip
from app.models.enums import TripDifficulty
from app.services.audit import who_label, write_audit
from app.services.finance import FinanceError


def adjust_trip(db, trip: Trip, actor, changes: dict) -> Trip:
    """แก้ข้อมูลทริปตาม changes (เฉพาะ field ที่ส่งมา) — edit_reason ถูก validate ที่ schema แล้ว"""
    edit_reason = (changes.get("edit_reason") or "").strip()
    if not edit_reason:
        raise FinanceError("ต้องระบุเหตุผลการแก้ไขทริปเสมอ")
    if trip.frozen:
        raise FinanceError(
            f"ทริป {trip.code} ถูกล็อกการเงินแล้ว — แก้ไม่ได้ ต้องขอปลดล็อก (Correction)"
        )

    applied: list[str] = []

    if changes.get("distance_km") is not None:
        trip.distance_km = round(float(changes["distance_km"]), 2)
        applied.append(f"ระยะทาง={trip.distance_km}")

    if changes.get("difficulty") is not None:
        trip.difficulty = TripDifficulty(changes["difficulty"])
        applied.append(f"ความยาก={trip.difficulty.value}")

    if changes.get("bonus") is not None:
        trip.bonus = round(float(changes["bonus"]), 2)
        applied.append(f"โบนัส={trip.bonus}")

    # เบี้ยเลี้ยงรายจุด — ตรวจว่า drop อยู่ในทริปนี้จริง
    allowances = changes.get("allowances")
    if allowances:
        drops_by_id = {d.id: d for d in trip.drops}
        for drop_id, amount in allowances.items():
            drop = drops_by_id.get(int(drop_id))
            if drop is None:
                raise FinanceError(f"จุดส่ง id={drop_id} ไม่อยู่ในทริป {trip.code}")
            if amount < 0:
                raise FinanceError("เบี้ยเลี้ยงติดลบไม่ได้")
            drop.allowance = round(float(amount), 2)
        applied.append(f"เบี้ยเลี้ยง {len(allowances)} จุด")

    # หักเงิน — ต้องมีเหตุผลของการหัก และห้ามเกินเพดาน (หลังปรับเบี้ยเลี้ยง/โบนัสข้างบนแล้ว)
    if changes.get("penalty") is not None:
        penalty = round(float(changes["penalty"]), 2)
        reason = (changes.get("penalty_reason") or "").strip()
        if penalty > 0 and not reason:
            raise FinanceError("ต้องระบุเหตุผลการหักเงินเมื่อแก้ยอดหัก")
        ceiling = round(sum(d.allowance for d in trip.drops), 2) + trip.bonus
        if penalty > ceiling:
            raise FinanceError(
                f"หักได้ไม่เกินเบี้ยเลี้ยงรวมของทริป ({ceiling:.2f}) — "
                "ห้ามหักเข้าค่าน้ำมันหรือเงินเดือน"
            )
        trip.penalty = penalty
        trip.penalty_reason = reason
        applied.append(f"หักเงิน={penalty}")

    if not applied:
        raise FinanceError("ไม่มีข้อมูลที่ต้องการแก้ไข")

    db.commit()
    db.refresh(trip)

    write_audit(
        db, who_label(actor), "แก้ไขข้อมูลทริป", trip.code,
        f"{' · '.join(applied)} · เหตุผล: {edit_reason}",
    )
    return trip
