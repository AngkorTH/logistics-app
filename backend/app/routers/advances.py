"""Router: Advance Payment — เบิกเงินล่วงหน้า (ข้อ 1.3)

- คนขับ: ยื่นขอเบิก + ดูรายการของตัวเอง
- Supervisor+ (รวม Admin/Super Admin เสมอ): ดูทั้งหมด + อนุมัติ/ปฏิเสธ
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_role, require_supervisor
from app.models import Advance, Role, User
from app.models.enums import AdvanceStatus
from app.schemas.ops import AdvanceCreateRequest, AdvanceOut
from app.services.advance import AdvanceError, decide_advance, request_advance

router = APIRouter(prefix="/advances", tags=["advances"])

require_driver = require_role(Role.DRIVER)


@router.post("", response_model=AdvanceOut)
def create(
    body: AdvanceCreateRequest,
    db: Session = Depends(get_db),
    driver: User = Depends(require_driver),
):
    """คนขับยื่นขอเบิกเงินล่วงหน้า"""
    try:
        return request_advance(db, driver, body.amount, body.reason)
    except AdvanceError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.get("", response_model=list[AdvanceOut])
def list_advances(
    status_filter: AdvanceStatus | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """รายการคำขอเบิก — Driver เห็นเฉพาะของตัวเอง / Supervisor+ เห็นทั้งหมด
    เรียงเก่า→ใหม่ (คิวอนุมัติ)"""
    q = db.query(Advance)
    if user.role is Role.DRIVER:
        q = q.filter(Advance.driver_id == user.id)
    if status_filter is not None:
        q = q.filter(Advance.status == status_filter)
    return q.order_by(Advance.id).all()


def _decide(advance_id: int, db: Session, actor: User, approve: bool) -> Advance:
    adv = db.get(Advance, advance_id)
    if not adv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบคำขอเบิกเงิน")
    try:
        return decide_advance(db, adv, actor, approve)
    except AdvanceError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/{advance_id}/approve", response_model=AdvanceOut)
def approve(
    advance_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_supervisor),
):
    """อนุมัติคำขอเบิก (Supervisor+) — ยอดจะถูกหักอัตโนมัติตอนล็อกการเงินทริป"""
    return _decide(advance_id, db, actor, True)


@router.post("/{advance_id}/reject", response_model=AdvanceOut)
def reject(
    advance_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_supervisor),
):
    """ปฏิเสธคำขอเบิก (Supervisor+)"""
    return _decide(advance_id, db, actor, False)
