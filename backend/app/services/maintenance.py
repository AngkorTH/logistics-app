"""Maintenance Report service — คนขับแจ้งเหตุ/รถมีปัญหา ตอนรองาน (สถานะขาว)

Flow:
- คนขับพิมพ์รายละเอียด + แนบรูป → เปิดรายการแจ้งเหตุ (OPEN)
- ตั้งรถประจำตัวเป็น MAINTENANCE → ล็อกไม่ให้คุมงานจ่ายงาน (assign_trip จะ 400)
- เด้งแจ้งเตือน (VEHICLE_ISSUE) เข้ากล่องคุมงาน/แอดมิน
- คุมงาน/แอดมินปิดเหตุ (RESOLVED) → ถ้าไม่มีเหตุ OPEN อื่นของรถคันนี้ ตั้งรถกลับ AVAILABLE
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import MaintenanceReport, Trip, User, Vehicle
from app.models.enums import IncidentStatus, TripStatus, VehicleStatus
from app.services.audit import who_label, write_audit
from app.services.notification import push_notification
from app.services.storage import save_photo_b64


class MaintenanceError(Exception):
    """คำขอแจ้ง/ปิดเหตุที่ทำไม่ได้ (สถานะผิดจังหวะ)"""


def report_issue(
    db: Session,
    driver: User,
    *,
    message: str,
    photo_b64: str,
    captured_at: datetime | None = None,
) -> MaintenanceReport:
    """คนขับแจ้งเหตุรถมีปัญหา → เปิดเหตุ + ล็อกรถเป็น MAINTENANCE + แจ้งเตือน"""
    # กันซ้อนกับ SOS: ถ้ากำลังมีทริปวิ่งอยู่ (ORANGE/GREEN) ให้ใช้ปุ่ม SOS แทน
    active = (
        db.query(Trip)
        .filter(
            Trip.driver_id == driver.id,
            Trip.status.in_([TripStatus.ORANGE, TripStatus.GREEN]),
        )
        .first()
    )
    if active:
        raise MaintenanceError(
            f"มีงานวิ่งอยู่ ({active.code}) — ระหว่างทริปให้ใช้ปุ่มแจ้งเหตุฉุกเฉิน (SOS) แทน"
        )

    vehicle = db.query(Vehicle).filter(Vehicle.driver_id == driver.id).first()

    code = f"MR-{db.query(MaintenanceReport).count() + 1:02d}"
    report = MaintenanceReport(
        code=code,
        driver_id=driver.id,
        vehicle_id=vehicle.id if vehicle else None,
        plate=vehicle.plate if vehicle else "",
        message=(message or "").strip(),
        photo=save_photo_b64(photo_b64, "maint"),
    )
    if captured_at is not None:
        report.created_at = captured_at

    # ล็อกรถ — คนคุมงานจ่ายงานคันนี้ไม่ได้จนกว่าจะปิดเหตุ
    if vehicle:
        vehicle.status = VehicleStatus.MAINTENANCE

    db.add(report)
    db.commit()
    db.refresh(report)

    plate_txt = vehicle.plate if vehicle else "ยังไม่ผูกรถ"
    write_audit(
        db, who_label(driver), "แจ้งเหตุรถมีปัญหา", plate_txt,
        f"{report.code} · {report.message or '—'}"
        + (" · ตั้งรถเป็นกำลังซ่อม" if vehicle else " · ไม่มีรถให้ล็อก"),
    )
    push_notification(
        db, "VEHICLE_ISSUE", f"🔧 แจ้งเหตุรถมีปัญหา · {plate_txt}",
        f"{who_label(driver)} · {report.message or 'ไม่มีรายละเอียด'}"
        + (" — รถถูกตั้งเป็นกำลังซ่อม จ่ายงานไม่ได้จนกว่าจะปิดเหตุ" if vehicle else ""),
    )
    return report


def resolve_report(
    db: Session, report: MaintenanceReport, actor: User, note: str = ""
) -> MaintenanceReport:
    """คุมงาน/แอดมินปิดเหตุ — ตั้งรถกลับ AVAILABLE เมื่อไม่มีเหตุ OPEN อื่นค้าง"""
    if report.status is not IncidentStatus.OPEN:
        raise MaintenanceError(f"เหตุ {report.code} ถูกปิดไปแล้ว")

    report.status = IncidentStatus.RESOLVED
    report.resolved_by = actor.id
    report.resolver_name = who_label(actor)
    report.resolver_note = (note or "").strip()
    report.resolved_at = datetime.now(timezone.utc)

    vehicle = db.get(Vehicle, report.vehicle_id) if report.vehicle_id else None
    still_open = 0
    if vehicle:
        still_open = (
            db.query(MaintenanceReport)
            .filter(
                MaintenanceReport.vehicle_id == vehicle.id,
                MaintenanceReport.status == IncidentStatus.OPEN,
                MaintenanceReport.id != report.id,
            )
            .count()
        )
        if not still_open:
            vehicle.status = VehicleStatus.AVAILABLE

    db.commit()
    db.refresh(report)

    write_audit(
        db, who_label(actor), "ปิดเหตุรถมีปัญหา", report.plate or "—",
        f"{report.code}" + (f" · {report.resolver_note}" if report.resolver_note else "")
        + ("" if still_open else " · รถกลับมาพร้อมใช้งาน"),
    )
    return report
