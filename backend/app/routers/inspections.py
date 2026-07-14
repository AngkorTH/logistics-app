"""Router: Pre-trip Inspection — ตรวจสภาพรถก่อนวิ่ง (ข้อ 1.2)

- คนขับเจ้าของทริปส่งผล checklist / ดูผลล่าสุดของทริปตัวเอง
- รายการรอประเมิน + การประเมิน = Supervisor ขึ้นไป (Admin/Super Admin เข้าถึงได้เสมอ)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_trip, require_supervisor
from app.models import Inspection, Role, Trip, User
from app.models.enums import InspectionStatus
from app.schemas.ops import InspectionOut, InspectionReviewRequest, InspectionSubmitRequest
from app.services.inspection import (
    InspectionError,
    latest_inspection,
    review_inspection,
    submit_inspection,
)

router = APIRouter(tags=["inspections"])


@router.post("/trips/{trip_id}/inspection", response_model=InspectionOut)
def submit(
    body: InspectionSubmitRequest,
    trip: Trip = Depends(get_trip),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """คนขับส่งผลตรวจสภาพรถ (เฉพาะเจ้าของทริป)"""
    if user.role is Role.DRIVER and trip.driver_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "ทำรายการได้เฉพาะทริปของตนเอง")
    try:
        return submit_inspection(
            db, trip, user, body.items,
            defect_note=body.defect_note, defect_photo_b64=body.defect_photo_b64,
        )
    except InspectionError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.get("/trips/{trip_id}/inspection", response_model=InspectionOut | None)
def latest(
    trip: Trip = Depends(get_trip),
    db: Session = Depends(get_db),
):
    """ผลตรวจล่าสุดของทริป (ownership เช็กแล้วใน get_trip) — null ถ้ายังไม่เคยตรวจ"""
    return latest_inspection(db, trip)


@router.get("/inspections/pending", response_model=list[InspectionOut])
def pending(
    db: Session = Depends(get_db),
    _: User = Depends(require_supervisor),
):
    """รายการชำรุดที่รอประเมิน (Supervisor+) — เรียงเก่า→ใหม่"""
    return (
        db.query(Inspection)
        .filter(Inspection.status == InspectionStatus.PENDING_REVIEW)
        .order_by(Inspection.id)
        .all()
    )


@router.post("/inspections/{inspection_id}/review", response_model=InspectionOut)
def review(
    inspection_id: int,
    body: InspectionReviewRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_supervisor),
):
    """ประเมินจุดชำรุด (Supervisor+): อนุมัติให้วิ่ง / ไม่อนุมัติ"""
    ins = db.get(Inspection, inspection_id)
    if not ins:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบรายการตรวจสภาพรถ")
    try:
        return review_inspection(db, ins, actor, body.approve, body.note)
    except InspectionError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
