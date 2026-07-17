"""Router: Maintenance Report — คนขับแจ้งเหตุ/รถมีปัญหา ตอนรองาน (สถานะขาว)

- คนขับ: แจ้งเหตุ (พิมพ์รายละเอียด + แนบรูป) → รถถูกตั้งเป็น MAINTENANCE
- Supervisor+ (รวม Admin/Super Admin): ดูรายการแจ้งเหตุ + ปิดเหตุ (ปลดล็อกรถ)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_supervisor
from app.models import MaintenanceReport, User
from app.models.enums import IncidentStatus
from app.schemas.ops import (
    MaintenanceReportOut,
    MaintenanceReportRequest,
    MaintenanceResolveRequest,
)
from app.services.maintenance import MaintenanceError, report_issue, resolve_report
from app.services.storage import StorageError

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


@router.post("/report", response_model=MaintenanceReportOut)
def report(
    body: MaintenanceReportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """คนขับแจ้งเหตุรถมีปัญหา → ล็อกรถเป็นกำลังซ่อม + แจ้งเตือนคุมงาน/แอดมิน"""
    try:
        return report_issue(
            db, user,
            message=body.message, photo_b64=body.photo_b64, captured_at=body.captured_at,
        )
    except (MaintenanceError, StorageError) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.get("", response_model=list[MaintenanceReportOut])
def list_reports(
    status_filter: IncidentStatus | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_supervisor),
):
    """รายการแจ้งเหตุรถมีปัญหา (Supervisor+) — เหตุเปิดขึ้นก่อน เรียงใหม่→เก่า"""
    q = db.query(MaintenanceReport)
    if status_filter is not None:
        q = q.filter(MaintenanceReport.status == status_filter)
    return q.order_by(MaintenanceReport.status.desc(), MaintenanceReport.id.desc()).all()


@router.post("/{report_id}/resolve", response_model=MaintenanceReportOut)
def resolve(
    report_id: int,
    body: MaintenanceResolveRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_supervisor),
):
    """ปิดเหตุ (Supervisor+) — ปลดล็อกรถกลับมาพร้อมใช้งานเมื่อไม่มีเหตุค้าง"""
    rep = db.get(MaintenanceReport, report_id)
    if not rep:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบรายการแจ้งเหตุ")
    try:
        return resolve_report(db, rep, actor, body.note)
    except MaintenanceError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
