"""Pre-trip Inspection — ตรวจสภาพรถก่อนวิ่ง (บังคับช่วง ORANGE)

Flow (ผู้ใช้ยืนยันแล้ว 2026-07-13):
- Supervisor จ่ายงาน → ORANGE ตามปกติ (state machine เดิมไม่แตะ)
- คนขับต้องส่ง checklist ตรวจสภาพรถ **ก่อน** จึงจะกด "ขนของขึ้นเสร็จ" (→GREEN) ได้
- ติ๊กผ่านทุกข้อ → PASSED เริ่มงานได้ทันที
- มีจุดชำรุด → บังคับแนบรูป → PENDING_REVIEW แจ้งคุมงาน/แอดมินประเมิน
  ปุ่มขนของขึ้นเสร็จถูกล็อก (hard-block) จนกว่าจะ APPROVED
"""
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Inspection, Trip, User
from app.models.enums import InspectionStatus, TripStatus
from app.services.audit import who_label, write_audit
from app.services.notification import push_notification


class InspectionError(Exception):
    """คำขอตรวจสภาพรถที่ทำไม่ได้ (สถานะผิดจังหวะ / ข้อมูลไม่ครบ)"""


def latest_inspection(db: Session, trip: Trip) -> Inspection | None:
    """ผลตรวจล่าสุดของทริป (ส่งซ้ำได้ — ยึดใบล่าสุดเป็นความจริง)"""
    return (
        db.query(Inspection)
        .filter(Inspection.trip_id == trip.id)
        .order_by(Inspection.id.desc())
        .first()
    )


def inspection_ready(db: Session, trip: Trip) -> bool:
    """ทริปนี้ผ่านด่านตรวจสภาพรถแล้วหรือยัง (PASSED หรือ APPROVED เท่านั้น)"""
    ins = latest_inspection(db, trip)
    return ins is not None and ins.status in (
        InspectionStatus.PASSED,
        InspectionStatus.APPROVED,
    )


def submit_inspection(
    db: Session,
    trip: Trip,
    driver: User,
    items: dict[str, bool],
    *,
    odometer_start: float,          # เลขไมล์ตอนเริ่ม (บังคับ — บันทึกลงทริปทันที)
    odometer_photo_b64: str,        # รูปหน้าปัดไมล์ (บังคับ)
    defect_note: str = "",
    defect_photo_b64: str | None = None,  # รูปจุดชำรุด (Phase 4 — บังคับเมื่อมีข้อไม่ผ่าน)
) -> Inspection:
    """คนขับส่งผล checklist ตรวจสภาพรถ + บันทึกเลขไมล์เริ่มพร้อมรูปหน้าปัด

    - เลขไมล์ + รูปหน้าปัดเป็นด่านบังคับ: ขาดข้อใดข้อหนึ่ง = ส่งผลตรวจไม่ได้
      (ค่าถูกเขียนลงทริปทันที ปุ่ม 'ขึ้นของเสร็จ' จึงไม่ต้องถามซ้ำ)
    - ผ่านครบทุกข้อ → PASSED
    - มีข้อไม่ผ่าน → บังคับแนบรูปจุดชำรุด → PENDING_REVIEW + แจ้งเตือนทีมคุมงาน
    """
    if trip.status is not TripStatus.ORANGE:
        raise InspectionError(
            f"ตรวจสภาพรถได้เฉพาะช่วงเตรียมขึ้นของ (ORANGE) — ทริป {trip.code} "
            f"อยู่สถานะ {trip.status.value}"
        )
    if not items:
        raise InspectionError("ต้องมีรายการ checklist อย่างน้อย 1 ข้อ")

    from app.services.storage import save_photo_b64
    from app.services.state_machine import TransitionError, _validate_odometer_start

    # ด่านเลขไมล์เริ่ม — ผิด/ขาด = ส่งผลตรวจไม่ได้เลย (ใช้กติกาเดียวกับ state machine)
    try:
        odo, odo_photo = _validate_odometer_start(db, trip, odometer_start, odometer_photo_b64)
    except TransitionError as e:
        raise InspectionError(str(e))

    all_pass = all(items.values())
    if not all_pass and not defect_photo_b64:
        raise InspectionError("มีจุดชำรุด — ต้องถ่ายรูปส่วนที่ชำรุดแนบไปให้คนคุมงานประเมิน")
    defect_photo = save_photo_b64(defect_photo_b64, "defect")

    ins = Inspection(
        trip_id=trip.id,
        driver_id=driver.id,
        items=json.dumps(items, ensure_ascii=False),
        passed=all_pass,
        defect_note=(defect_note or "").strip(),
        defect_photo=defect_photo,
        status=InspectionStatus.PASSED if all_pass else InspectionStatus.PENDING_REVIEW,
    )
    db.add(ins)
    # เขียนเลขไมล์เริ่ม + รูปหน้าปัดลงทริปใน transaction เดียวกับผลตรวจ
    trip.odometer_start = odo
    trip.odometer_start_photo = odo_photo
    db.commit()
    db.refresh(ins)

    failed = [k for k, v in items.items() if not v]
    write_audit(
        db, who_label(driver), "ตรวจสภาพรถก่อนวิ่ง", trip.code,
        ("ผ่านทุกข้อ" if all_pass else f"พบจุดชำรุด: {', '.join(failed)} · รอประเมิน")
        + f" · เลขไมล์เริ่ม {odo:.1f} (แนบรูปหน้าปัด)",
    )
    if not all_pass:
        push_notification(
            db, "INSPECTION_DEFECT", f"รถมีจุดชำรุด · {trip.code}",
            f"{who_label(driver)} รายงานจุดชำรุด: {', '.join(failed)}"
            + (f" · {ins.defect_note}" if ins.defect_note else ""),
            trip.id,
        )
    return ins


def review_inspection(
    db: Session, ins: Inspection, actor: User, approve: bool, note: str = ""
) -> Inspection:
    """คุมงาน/แอดมินประเมินรายการชำรุด — APPROVED ให้วิ่งได้ / REJECTED ห้ามวิ่ง"""
    if ins.status is not InspectionStatus.PENDING_REVIEW:
        raise InspectionError(
            f"รายการตรวจนี้อยู่สถานะ {ins.status.value} — ประเมินได้เฉพาะรายการที่รอประเมิน"
        )

    ins.status = InspectionStatus.APPROVED if approve else InspectionStatus.REJECTED
    ins.reviewed_by = actor.id
    ins.reviewer_name = who_label(actor)
    ins.reviewed_at = datetime.now(timezone.utc)
    if note and note.strip():
        ins.defect_note = (ins.defect_note + f" · ผู้ประเมิน: {note.strip()}").strip(" ·")
    db.commit()
    db.refresh(ins)

    write_audit(
        db, who_label(actor), "ประเมินผลตรวจสภาพรถ", ins.trip.code,
        ("อนุมัติให้วิ่งได้" if approve else "ไม่อนุมัติ — รถต้องซ่อมก่อน")
        + (f" · {note.strip()}" if note and note.strip() else ""),
    )
    return ins
