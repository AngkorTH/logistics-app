"""บริการบันทึก Audit Trail — ใคร / ทำอะไร / ข้อมูลไหน / เวลาใด

ใช้ได้ทั้งจากใน endpoint (บันทึกรายละเอียดเชิงธุรกิจ) และจาก middleware (บันทึกดักจับทั่วไป)
"""
from sqlalchemy.orm import Session

from app.models import AuditLog, User


def write_audit(db: Session, who: str, action: str, target: str = "—", detail: str = "") -> AuditLog:
    log = AuditLog(who=who, action=action, target=target, detail=detail)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def who_label(user: User | None) -> str:
    """รูปแบบมาตรฐานของผู้กระทำ เช่น 'ธนพล คุมงาน (SV01)'"""
    if not user:
        return "ระบบ"
    return f"{user.name} ({user.emp_id})"
