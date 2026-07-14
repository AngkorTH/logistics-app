"""Router: Penalty (หลายรายการ) — บันทึก/ดูเงินหัก (Supervisor+)

⚠️ Driver เข้าถึงไม่ได้ — ใช้ require_supervisor เท่านั้น (ไม่ผูก ownership แบบ Driver)
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_supervisor
from app.models import Penalty, Trip, User
from app.schemas.management import (
    DeductionLeaderRow,
    PenaltyCreate,
    PenaltyListRow,
    PenaltyOut,
)
from app.services.finance import FinanceError
from app.services.penalty import add_penalty, deduction_leaderboard

router = APIRouter(tags=["penalty"])


def _get_trip_admin(trip_id: int, db: Session) -> Trip:
    """โหลดทริปแบบไม่ผูก ownership (endpoint ชุดนี้ Supervisor+ เท่านั้นอยู่แล้ว)"""
    trip = db.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบทริป")
    return trip


@router.post("/trips/{trip_id}/penalties", response_model=PenaltyOut)
def create_penalty(
    trip_id: int,
    body: PenaltyCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_supervisor),
):
    """เพิ่มรายการหักเงิน (Supervisor+): บังคับเหตุผล · หักจากเบี้ยเลี้ยงเท่านั้น"""
    trip = _get_trip_admin(trip_id, db)
    try:
        return add_penalty(db, trip, actor, body.amount, body.reason)
    except FinanceError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.get("/trips/{trip_id}/penalties", response_model=list[PenaltyOut])
def list_trip_penalties(
    trip_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_supervisor),
):
    """รายการหักเงินของทริปหนึ่ง (Supervisor+)"""
    _get_trip_admin(trip_id, db)
    return db.query(Penalty).filter(Penalty.trip_id == trip_id).order_by(Penalty.id).all()


@router.get("/penalties/leaderboard", response_model=list[DeductionLeaderRow])
def penalty_leaderboard(
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    _: User = Depends(require_supervisor),
):
    """จัดอันดับการหักเงินรายเดือน (task 3): group by คนขับ → ยอดรวม + จำนวนครั้ง เรียงมาก→น้อย"""
    return deduction_leaderboard(db, year, month)


@router.get("/penalties", response_model=list[PenaltyListRow])
def list_all_penalties(
    driver_name: str | None = None,
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    _: User = Depends(require_supervisor),
):
    """ตารางประวัติ/สรุปการหักเงิน (หน้าแยกเฉพาะ) — กรองด้วยชื่อคนขับ + เดือน/ปี

    - driver_name : ค้นหาชื่อคนขับแบบ substring (case-insensitive)
    - month/year  : กรองตามเวลาที่บันทึกการหักเงิน (Penalty.created_at)
    """
    query = (
        db.query(Penalty, User.name, Trip.code)
        .join(User, Penalty.driver_id == User.id)
        .join(Trip, Penalty.trip_id == Trip.id)
    )
    if driver_name and driver_name.strip():
        query = query.filter(func.lower(User.name).contains(driver_name.strip().lower()))
    if year is not None:
        query = query.filter(extract("year", Penalty.created_at) == year)
    if month is not None:
        query = query.filter(extract("month", Penalty.created_at) == month)
    rows = query.order_by(Penalty.created_at.desc()).all()
    return [
        PenaltyListRow(
            id=p.id, trip_id=p.trip_id, driver_id=p.driver_id, amount=p.amount,
            reason=p.reason, creator_name=p.creator_name, created_at=p.created_at,
            driver_name=driver_name, trip_code=trip_code,
        )
        for p, driver_name, trip_code in rows
    ]
