"""Notification service — เขียน/อ่านกล่องจดหมายฝั่งบริหาร

ใช้ push_notification() ทุกจุดที่ต้องการแจ้งทีมคุมงาน เช่น
- คนขับส่งภาพบิลเข้ามา (BILL_UPLOADED)
- ทริปจบงานอัตโนมัติ (TRIP_DONE)
ยัง print stub ไว้ด้วย (เผื่อต่อ push จริงภายหลัง) แต่หลักคือบันทึกลง DB เป็น inbox
"""
from sqlalchemy.orm import Session

from app.models import Notification


def push_notification(
    db: Session, kind: str, title: str, message: str = "", trip_id: int | None = None
) -> Notification:
    """สร้างแจ้งเตือน 1 รายการเข้ากล่องจดหมายบริหาร"""
    n = Notification(kind=kind, title=title, message=message, trip_id=trip_id)
    db.add(n)
    db.commit()
    db.refresh(n)
    print(f"[INBOX] {kind} · {title} · {message}")
    return n
