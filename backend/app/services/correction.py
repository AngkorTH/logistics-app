"""Freeze & Correction Workflow — ปลดล็อกแก้ตัวเลขการเงินที่ freeze แล้ว (skill.md ข้อ 4)

หลังปิดงาน (close_trip) ยอดเงินทั้งทริปถูก freeze ถาวร แก้ผ่านหน้าปกติไม่ได้
ทางเดียวที่จะแก้คือ:
    1) Supervisor กด "ขอปลดล็อก" (request_correction) พร้อม **เหตุผลบังคับ** + ค่าเก่า/ใหม่
       → สร้าง Correction สถานะ PENDING (ยังไม่แตะตัวเลขจริง)
    2) **Super Admin เท่านั้น** อนุมัติ (approve_correction) → เขียนค่าใหม่ลงทริป + log
       หรือ ปฏิเสธ (reject_correction) → ตัวเลขคงเดิม

Field ที่แก้ได้: fuel / toll / bonus / penalty / allowance:<dropId>
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Correction, Drop, Trip
from app.models.enums import CorrectionStatus, Role
from app.services.audit import who_label, write_audit


class CorrectionError(Exception):
    """คำขอ/การอนุมัติปลดล็อกที่ทำไม่ได้ (สิทธิ์ไม่พอ / เหตุผลว่าง / ทริปไม่ freeze ฯลฯ)"""


# label ไทยของแต่ละ field เพื่อบันทึกให้อ่านง่าย
_FIELD_LABEL = {
    "fuel": "ค่าน้ำมัน",
    "toll": "ค่าทางหลวง",
    "bonus": "โบนัส",
    "penalty": "ยอดหักเงิน",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_field(trip: Trip, field_key: str) -> tuple[str, float, object, str]:
    """แปลง field_key → (label, ค่าปัจจุบัน, object เป้าหมาย, ชื่อ attribute)

    รองรับ allowance รายจุดผ่านรูปแบบ 'allowance:<dropId>'
    """
    if field_key.startswith("allowance:"):
        drop_id = int(field_key.split(":", 1)[1])
        drop = next((d for d in trip.drops if d.id == drop_id), None)
        if drop is None:
            raise CorrectionError(f"ไม่พบจุดส่ง id={drop_id} ในทริป {trip.code}")
        return (f"เบี้ยเลี้ยงจุด {drop.seq}", drop.allowance, drop, "allowance")

    mapping = {
        "fuel": (trip, "frozen_fuel"),
        "toll": (trip, "frozen_toll"),
        "bonus": (trip, "bonus"),
        "penalty": (trip, "penalty"),
    }
    if field_key not in mapping:
        raise CorrectionError(f"field '{field_key}' แก้ไขไม่ได้")
    obj, attr = mapping[field_key]
    current = getattr(obj, attr) or 0.0
    return (_FIELD_LABEL[field_key], current, obj, attr)


def request_correction(
    db: Session, trip: Trip, requester, field_key: str, new_val: float, reason: str
) -> Correction:
    """Supervisor ขอปลดล็อกแก้ตัวเลข 1 field — บันทึกเป็นคำขอ PENDING (ยังไม่แก้จริง)

    การ์ด: ทริปต้อง freeze แล้ว และเหตุผลบังคับกรอก
    """
    if not trip.frozen:
        raise CorrectionError(
            f"ทริป {trip.code} ยังไม่ถูกล็อก (freeze) — แก้ผ่านหน้าปกติได้ ไม่ต้องขอปลดล็อก"
        )
    if not reason or not reason.strip():
        raise CorrectionError("ต้องระบุเหตุผลการขอปลดล็อกเสมอ")

    label, old_val, _obj, _attr = _resolve_field(trip, field_key)

    n = db.query(Correction).count() + 1
    corr = Correction(
        code=f"C-{n:02d}",
        trip_id=trip.id,
        requested_by=requester.id,
        requester_name=who_label(requester),
        field_key=field_key,
        field_label=label,
        old_val=float(old_val),
        new_val=float(new_val),
        reason=reason.strip(),
        status=CorrectionStatus.PENDING,
    )
    db.add(corr)
    db.commit()
    db.refresh(corr)

    write_audit(
        db, who_label(requester), "ขอปลดล็อกการเงิน", trip.code,
        f"{corr.code} · {label} {old_val:.2f} → {new_val:.2f} · เหตุผล: {corr.reason}",
    )
    return corr


def approve_correction(db: Session, corr: Correction, approver) -> Correction:
    """Super Admin อนุมัติ → เขียนค่าใหม่ลงทริปจริง + ปลด/คงสถานะ freeze

    การ์ด: ต้องเป็น SUPER_ADMIN เท่านั้น และคำขอยังต้อง PENDING
    """
    if approver.role is not Role.SUPER_ADMIN:
        raise CorrectionError("เฉพาะ Super Admin เท่านั้นที่อนุมัติการปลดล็อกการเงินได้")
    if corr.status is not CorrectionStatus.PENDING:
        raise CorrectionError(f"คำขอ {corr.code} ถูกตัดสินไปแล้ว ({corr.status.value})")

    trip = db.get(Trip, corr.trip_id)
    _label, _old, obj, attr = _resolve_field(trip, corr.field_key)
    setattr(obj, attr, corr.new_val)  # เขียนค่าใหม่ลงตัวเลขที่เคย freeze

    corr.status = CorrectionStatus.APPROVED
    corr.approved_by = approver.id
    corr.approved_at = _now()
    db.commit()
    db.refresh(corr)

    write_audit(
        db, who_label(approver), "อนุมัติปลดล็อกการเงิน", trip.code,
        f"{corr.code} · {corr.field_label} {corr.old_val:.2f} → {corr.new_val:.2f}",
    )
    return corr


def reject_correction(db: Session, corr: Correction, approver, reason: str = "") -> Correction:
    """Super Admin ปฏิเสธคำขอ → ตัวเลขคงเดิม บันทึก log"""
    if approver.role is not Role.SUPER_ADMIN:
        raise CorrectionError("เฉพาะ Super Admin เท่านั้นที่ตัดสินการปลดล็อกได้")
    if corr.status is not CorrectionStatus.PENDING:
        raise CorrectionError(f"คำขอ {corr.code} ถูกตัดสินไปแล้ว ({corr.status.value})")

    corr.status = CorrectionStatus.REJECTED
    corr.approved_by = approver.id
    corr.approved_at = _now()
    db.commit()
    db.refresh(corr)

    write_audit(
        db, who_label(approver), "ปฏิเสธปลดล็อกการเงิน",
        db.get(Trip, corr.trip_id).code,
        f"{corr.code} · {corr.field_label}" + (f" · {reason}" if reason else ""),
    )
    return corr
