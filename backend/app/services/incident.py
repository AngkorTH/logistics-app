"""SOS / Incident Report — แจ้งเหตุฉุกเฉินระหว่างทริป (ข้อ 1.4)

Flow:
- คนขับกด SOS ระหว่างทริปที่กำลังวิ่ง (ORANGE/GREEN): แนบชนิดเหตุ + ข้อความ + พิกัด + รูป
- ทริปถูกล็อกสถานะชั่วคราว (Trip.paused = True) — กดขนของเสร็จ/ส่งของไม่ได้จนกว่าปิดเหตุ
- แจ้งเตือนสีแดง (kind="SOS") เด้งเข้ากล่องคุมงาน/แอดมินทันที
- คุมงาน/แอดมินปิดเหตุ (RESOLVED) → ปลด pause ถ้าไม่มีเหตุอื่นค้างอยู่
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Incident, Trip, User
from app.models.enums import IncidentKind, IncidentStatus, TripStatus
from app.services.audit import who_label, write_audit
from app.services.notification import push_notification
from app.services.storage import save_photo_b64


class IncidentError(Exception):
    """คำขอแจ้ง/ปิดเหตุที่ทำไม่ได้ (สถานะผิดจังหวะ)"""


def report_sos(
    db: Session,
    trip: Trip,
    driver: User,
    kind: IncidentKind,
    *,
    message: str = "",
    gps: str | None = None,
    photo_b64: str | None = None,  # รูปหน้างาน (Phase 4)
    captured_at: datetime | None = None,  # เวลากดแจ้งเหตุจริงตอนออฟไลน์
) -> Incident:
    """คนขับแจ้งเหตุฉุกเฉิน → เปิดเหตุ + pause ทริป + แจ้งเตือนแดง"""
    if trip.status not in (TripStatus.ORANGE, TripStatus.GREEN):
        raise IncidentError(
            f"แจ้งเหตุได้เฉพาะทริปที่กำลังวิ่ง (ORANGE/GREEN) — ทริป {trip.code} "
            f"อยู่สถานะ {trip.status.value}"
        )

    code = f"S-{db.query(Incident).count() + 1:02d}"
    inc = Incident(
        code=code,
        trip_id=trip.id,
        driver_id=driver.id,
        kind=kind,
        message=(message or "").strip(),
        gps=gps,
        photo=save_photo_b64(photo_b64, "sos"),
    )
    if captured_at is not None:
        inc.created_at = captured_at
    trip.paused = True
    db.add(inc)
    db.commit()
    db.refresh(inc)

    write_audit(
        db, who_label(driver), "แจ้งเหตุฉุกเฉิน (SOS)", trip.code,
        f"{kind.value} · {inc.message or '—'}" + (f" · GPS {gps}" if gps else ""),
    )
    push_notification(
        db, "SOS", f"🚨 เหตุฉุกเฉิน {kind.value} · {trip.code}",
        f"{who_label(driver)} · {inc.message or 'ไม่มีรายละเอียด'}"
        + (f" · พิกัด {gps}" if gps else ""),
        trip.id,
    )
    return inc


def resolve_incident(db: Session, inc: Incident, actor: User, note: str = "") -> Incident:
    """คุมงาน/แอดมินปิดเหตุ — ปลด pause ทริปเมื่อไม่มีเหตุ OPEN อื่นค้าง"""
    if inc.status is not IncidentStatus.OPEN:
        raise IncidentError(f"เหตุ {inc.code} ถูกปิดไปแล้ว")

    inc.status = IncidentStatus.RESOLVED
    inc.resolved_by = actor.id
    inc.resolver_name = who_label(actor)
    inc.resolved_at = datetime.now(timezone.utc)

    still_open = (
        db.query(Incident)
        .filter(
            Incident.trip_id == inc.trip_id,
            Incident.status == IncidentStatus.OPEN,
            Incident.id != inc.id,
        )
        .count()
    )
    if not still_open:
        inc.trip.paused = False
    db.commit()
    db.refresh(inc)

    write_audit(
        db, who_label(actor), "ปิดเหตุฉุกเฉิน", inc.trip.code,
        f"{inc.code} · {inc.kind.value}" + (f" · {note.strip()}" if note.strip() else "")
        + ("" if still_open else " · ทริปวิ่งต่อได้"),
    )
    return inc
