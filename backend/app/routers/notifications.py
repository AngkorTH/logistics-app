"""Router: Notifications — กล่องจดหมายแจ้งเตือนฝั่งบริหาร (Supervisor+)

⚠️ Driver เข้าถึงไม่ได้ — ใช้ require_supervisor
แจ้งเตือนถูกเขียนอัตโนมัติจากทั่วระบบ (บิลใหม่, ทริปจบงานอัตโนมัติ ฯลฯ)
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_supervisor
from app.models import Notification, User
from app.schemas.management import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notification"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    unread: bool = False,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_supervisor),
):
    """กล่องจดหมายบริหาร (Supervisor+) — เรียงใหม่→เก่า · unread=true ดูเฉพาะที่ยังไม่อ่าน"""
    q = db.query(Notification)
    if unread:
        q = q.filter(Notification.read.is_(False))
    return q.order_by(Notification.at.desc(), Notification.id.desc()).limit(limit).all()


@router.post("/{notif_id}/read", response_model=NotificationOut)
def mark_read(
    notif_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_supervisor),
):
    """ทำเครื่องหมายว่าอ่านแล้ว 1 รายการ"""
    n = db.get(Notification, notif_id)
    if not n:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบการแจ้งเตือน")
    n.read = True
    db.commit()
    db.refresh(n)
    return n


@router.post("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    _: User = Depends(require_supervisor),
):
    """ทำเครื่องหมายอ่านทั้งหมด"""
    updated = db.query(Notification).filter(Notification.read.is_(False)).update({Notification.read: True})
    db.commit()
    return {"updated": updated}
