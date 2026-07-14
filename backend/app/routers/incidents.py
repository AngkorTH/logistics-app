"""Router: SOS / Incident Report — แจ้งเหตุฉุกเฉินระหว่างทริป (ข้อ 1.4)

- คนขับเจ้าของทริป: กด SOS
- Supervisor+ (รวม Admin/Super Admin เสมอ): ดูรายการเหตุ + ปิดเหตุ
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_trip, require_supervisor
from app.models import Incident, Role, Trip, User
from app.models.enums import IncidentStatus
from app.schemas.ops import IncidentOut, IncidentResolveRequest, SosRequest
from app.services.incident import IncidentError, report_sos, resolve_incident

router = APIRouter(tags=["incidents"])


@router.post("/trips/{trip_id}/sos", response_model=IncidentOut)
def sos(
    body: SosRequest,
    trip: Trip = Depends(get_trip),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """คนขับแจ้งเหตุฉุกเฉิน (เฉพาะเจ้าของทริป) → pause ทริป + แจ้งเตือนแดง"""
    if user.role is Role.DRIVER and trip.driver_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "ทำรายการได้เฉพาะทริปของตนเอง")
    gps = f"{body.lat:.5f},{body.lng:.5f}" if body.lat is not None and body.lng is not None else None
    try:
        return report_sos(
            db, trip, user, body.kind,
            message=body.message, gps=gps, photo_b64=body.photo_b64,
            captured_at=body.captured_at,
        )
    except IncidentError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.get("/incidents", response_model=list[IncidentOut])
def list_incidents(
    status_filter: IncidentStatus | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_supervisor),
):
    """รายการเหตุฉุกเฉิน (Supervisor+) — เหตุเปิดขึ้นก่อน เรียงใหม่→เก่า"""
    q = db.query(Incident)
    if status_filter is not None:
        q = q.filter(Incident.status == status_filter)
    return q.order_by(Incident.status.desc(), Incident.id.desc()).all()


@router.post("/incidents/{incident_id}/resolve", response_model=IncidentOut)
def resolve(
    incident_id: int,
    body: IncidentResolveRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_supervisor),
):
    """ปิดเหตุ (Supervisor+) — ปลด pause ทริปเมื่อไม่มีเหตุค้าง"""
    inc = db.get(Incident, incident_id)
    if not inc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบเหตุฉุกเฉิน")
    try:
        return resolve_incident(db, inc, actor, body.note)
    except IncidentError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
