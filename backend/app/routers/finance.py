"""Router: Financial Operations — เบี้ยเลี้ยง / โบนัส / หักเงิน

- ดูสรุปการเงิน: ownership ปกติ (Driver เห็นของตัวเอง)
- ตั้งยอดหัก/โบนัส = Supervisor+ เท่านั้น (หักเงินต้องมีเหตุผลเสมอ, หักจากเบี้ยเลี้ยงรวม)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_trip, require_supervisor
from app.models import Trip, User
from app.schemas.ops import BonusRequest, FinanceOut, PenaltyRequest
from app.services.finance import (
    FinanceError,
    apply_penalty,
    compute_finance,
    set_bonus,
)

router = APIRouter(prefix="/trips", tags=["finance"])


@router.get("/{trip_id}/finance", response_model=FinanceOut)
def get_finance(trip: Trip = Depends(get_trip)):
    """สรุปการเงินของทริป (ownership เช็กใน get_trip)"""
    return FinanceOut(**compute_finance(trip).__dict__)


@router.post("/{trip_id}/penalty", response_model=FinanceOut)
def apply_penalty_ep(
    body: PenaltyRequest,
    trip: Trip = Depends(get_trip),
    db: Session = Depends(get_db),
    actor: User = Depends(require_supervisor),
):
    """ตั้งยอดหักเงิน (Supervisor+): บังคับเหตุผล, หักจากเบี้ยเลี้ยงรวมเท่านั้น"""
    try:
        apply_penalty(db, trip, actor, body.amount, body.reason)
    except FinanceError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return FinanceOut(**compute_finance(trip).__dict__)


@router.post("/{trip_id}/bonus", response_model=FinanceOut)
def set_bonus_ep(
    body: BonusRequest,
    trip: Trip = Depends(get_trip),
    db: Session = Depends(get_db),
    actor: User = Depends(require_supervisor),
):
    """ตั้งโบนัสระดับทริป (Supervisor+)"""
    try:
        set_bonus(db, trip, actor, body.amount)
    except FinanceError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return FinanceOut(**compute_finance(trip).__dict__)
