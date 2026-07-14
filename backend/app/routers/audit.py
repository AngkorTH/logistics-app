"""Router: Audit Log (อ่าน) — ประวัติเหตุการณ์สำคัญทั้งระบบ (task 5)

⚠️ Admin+ เท่านั้น (require_admin) — Supervisor/Driver เข้าไม่ได้
ตารางบันทึกอัตโนมัติจากทั่วระบบผ่าน services.audit.write_audit
(รวมถึง task 1 เปลี่ยนสถานะ และ task 2 แก้ยอดเงิน OCR)
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.models import AuditLog, User
from app.schemas.management import AuditLogOut

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=list[AuditLogOut])
def list_audit_logs(
    action: str | None = None,
    target: str | None = None,
    who: str | None = None,
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None, ge=2000, le=2600),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """ประวัติเหตุการณ์ล่าสุด (Admin+ เท่านั้น — 'ประวัติการแก้' ข้อ 3.1)
    กรองด้วย action/target/who (substring) + เดือน/ปี ค.ศ. ได้, เรียงใหม่→เก่า"""
    q = db.query(AuditLog)
    if action and action.strip():
        q = q.filter(AuditLog.action.contains(action.strip()))
    if target and target.strip():
        q = q.filter(AuditLog.target.contains(target.strip()))
    if who and who.strip():
        q = q.filter(AuditLog.who.contains(who.strip()))
    # กรองเดือน/ปีด้วยช่วงเวลา — ปีอย่างเดียวได้ / ปี+เดือนได้ (เดือนเดี่ยวๆ ไม่กรอง)
    if year is not None:
        from datetime import datetime, timezone

        start = datetime(year, month or 1, 1, tzinfo=timezone.utc)
        if month is None or month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
        q = q.filter(AuditLog.at >= start, AuditLog.at < end)
    return q.order_by(AuditLog.at.desc(), AuditLog.id.desc()).limit(limit).all()
