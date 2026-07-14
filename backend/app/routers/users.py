"""Router: User Management + Driver Rating + Monthly Trip History

⚠️ Driver เข้าถึงไม่ได้:
- ดู/แก้พนักงาน + ให้ดาว = Admin+  (require_admin)
- ประวัติทริปรายเดือน       = Supervisor+ (require_supervisor)
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin, require_supervisor
from app.models import User
from app.models.enums import Role
from app.schemas.management import (
    MonthlyHistoryOut,
    RatingRequest,
    UserManageOut,
    UserUpdate,
)
from app.services.management import (
    ManageError,
    monthly_history,
    monthly_trip_rows,
    set_rating,
    update_user,
)

router = APIRouter(prefix="/users", tags=["users"])


def _get_user(user_id: int, db: Session) -> User:
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบพนักงาน")
    return u


@router.get("", response_model=list[UserManageOut])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """รายชื่อพนักงานทั้งหมด (Admin+)"""
    return db.query(User).order_by(User.emp_id).all()


@router.patch("/{user_id}", response_model=UserManageOut)
def edit_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    """แก้ข้อมูลส่วนตัวพนักงาน (Admin+)"""
    target = _get_user(user_id, db)
    try:
        return update_user(db, target, actor, body.model_dump(exclude_unset=True))
    except ManageError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/{user_id}/rating", response_model=UserManageOut)
def rate_driver(
    user_id: int,
    body: RatingRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    """ให้ดาวคนขับ 0-5 (Admin+) — Frontend แสดงเป็นดาวเท่านั้น"""
    target = _get_user(user_id, db)
    try:
        return set_rating(db, target, actor, body.rating)
    except ManageError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.get("/{user_id}/history/monthly", response_model=MonthlyHistoryOut)
def driver_monthly_history(
    user_id: int,
    year: int | None = Query(None, ge=2000, le=2100),
    month: int | None = Query(None, ge=1, le=12),
    db: Session = Depends(get_db),
    _: User = Depends(require_supervisor),
):
    """ประวัติทริปรายเดือนของคนขับ (Supervisor+)

    - ไม่ส่ง param    → สรุปรายเดือน (months) สำหรับ Month/Year Picker
    - ส่ง year+month → เพิ่มตารางทริปรายเที่ยว (trips) ของเดือนนั้น
      (flow: เลือกคนขับ → เลือกเดือน/ปี → แสดงตาราง)
    """
    target = _get_user(user_id, db)
    if target.role is not Role.DRIVER:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ดูประวัติทริปได้เฉพาะพนักงานขับรถ")
    trips = []
    if year is not None and month is not None:
        trips = monthly_trip_rows(db, target, year, month)
    return MonthlyHistoryOut(
        driver_id=target.id,
        driver_name=target.name,
        months=monthly_history(db, target),
        trips=trips,
    )
