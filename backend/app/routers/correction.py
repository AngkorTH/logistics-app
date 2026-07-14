"""Router: Freeze & Correction — ปลดล็อกแก้ตัวเลขการเงินที่ freeze แล้ว

- ขอปลดล็อก (request) = Supervisor+ (ต้องมีเหตุผล, ทริปต้อง freeze แล้ว)
- อนุมัติ / ปฏิเสธ = **Super Admin เท่านั้น** (require_super_admin) ตาม claude.md ข้อ 2
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_trip, require_super_admin, require_supervisor
from app.models import Correction, Trip, User
from app.models.enums import CorrectionStatus
from app.schemas.ops import CorrectionOut, CorrectionRequest, RejectRequest
from app.services.correction import (
    CorrectionError,
    approve_correction,
    reject_correction,
    request_correction,
)

router = APIRouter(tags=["correction"])


def _get_pending(db: Session, correction_id: int) -> Correction:
    corr = db.get(Correction, correction_id)
    if not corr:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบคำขอปลดล็อก")
    return corr


@router.post("/trips/{trip_id}/corrections", response_model=CorrectionOut)
def request_correction_ep(
    body: CorrectionRequest,
    trip: Trip = Depends(get_trip),
    db: Session = Depends(get_db),
    requester: User = Depends(require_supervisor),
):
    """Supervisor+ ขอปลดล็อกแก้ตัวเลข 1 field → สร้างคำขอ PENDING"""
    try:
        return request_correction(
            db, trip, requester, body.field_key, body.new_val, body.reason
        )
    except CorrectionError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.get("/corrections", response_model=list[CorrectionOut])
def list_corrections(
    db: Session = Depends(get_db),
    _: User = Depends(require_supervisor),
    status_filter: CorrectionStatus | None = None,
):
    """รายการคำขอปลดล็อก (Supervisor+) — กรองตามสถานะได้"""
    q = db.query(Correction)
    if status_filter is not None:
        q = q.filter(Correction.status == status_filter)
    return q.order_by(Correction.id.desc()).all()


@router.post("/corrections/{correction_id}/approve", response_model=CorrectionOut)
def approve_correction_ep(
    correction_id: int,
    db: Session = Depends(get_db),
    approver: User = Depends(require_super_admin),
):
    """อนุมัติปลดล็อก — Super Admin เท่านั้น → เขียนค่าใหม่ลงทริปจริง"""
    corr = _get_pending(db, correction_id)
    try:
        return approve_correction(db, corr, approver)
    except CorrectionError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/corrections/{correction_id}/reject", response_model=CorrectionOut)
def reject_correction_ep(
    correction_id: int,
    body: RejectRequest,
    db: Session = Depends(get_db),
    approver: User = Depends(require_super_admin),
):
    """ปฏิเสธคำขอปลดล็อก — Super Admin เท่านั้น → ตัวเลขคงเดิม"""
    corr = _get_pending(db, correction_id)
    try:
        return reject_correction(db, corr, approver, body.reason)
    except CorrectionError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
