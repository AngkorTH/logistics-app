"""Router: Evidence & OCR — 4 ปุ่มหลักฐานต่อ 1 จุดส่ง

- อัปบิลน้ำมัน/ทางหลวง (Driver เจ้าของ หรือ Supervisor) → OCR draft (ห้าม auto-commit)
- อนุมัติบิล = Supervisor+ เท่านั้น (ยืนยันยอด draft เข้ายอดจริง)
- รูปผ้าใบ / รูปส่งของสำเร็จ = Driver เจ้าของทริป (ผูก GPS ปลายทางตอนส่งสำเร็จ)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_drop, require_supervisor
from app.models import Drop, Receipt, Role, User
from app.schemas.ops import (
    DeliveryRequest,
    DropOut,
    ReceiptApproveRequest,
    ReceiptEditRequest,
    ReceiptOut,
    ReceiptUploadRequest,
    TarpUploadRequest,
)
from app.services.evidence import (
    EvidenceError,
    approve_receipt,
    edit_receipt_amount,
    upload_receipt,
    upload_tarp,
)
from app.services.state_machine import TransitionError, record_delivery
from app.services.storage import StorageError

router = APIRouter(tags=["evidence"])


def _assert_own_driver(drop: Drop, user: User) -> None:
    if user.role is Role.DRIVER and drop.trip.driver_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "ทำรายการได้เฉพาะทริปของตนเอง")


@router.post("/drops/{drop_id}/receipt", response_model=ReceiptOut)
def upload_receipt_ep(
    body: ReceiptUploadRequest,
    drop: Drop = Depends(get_drop),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """อัปรูปบิลน้ำมัน/ทางหลวงรายจุด → Receipt draft (ยอด 0 · ไม่มี OCR)

    คนขับส่งแค่รูป · ยอดเงิน + วันที่ Supervisor กรอกเองตอนยืนยัน
    """
    _assert_own_driver(drop, user)
    try:
        return upload_receipt(
            db, drop, user, body.kind,
            captured_at=body.captured_at, photo_b64=body.photo_b64,
            liters=body.liters,
        )
    except (EvidenceError, StorageError) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/receipts/{receipt_id}/approve", response_model=ReceiptOut)
def approve_receipt_ep(
    receipt_id: int,
    body: ReceiptApproveRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_supervisor),
):
    """ยืนยันบิล (Supervisor+) — เปิดรูปดูแล้ว **กรอกยอดเงิน + วันที่เอง** → นับเข้ายอดจริง"""
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบบิล")
    try:
        return approve_receipt(db, receipt, actor, amount=body.amount, date=body.date)
    except EvidenceError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.patch("/receipts/{receipt_id}/amount", response_model=ReceiptOut)
def edit_receipt_amount_ep(
    receipt_id: int,
    body: ReceiptEditRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_supervisor),
):
    """แก้ยอดเงินใบเสร็จ OCR แบบ Manual (Supervisor+) — บังคับ new_amount + reason (task 2)"""
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบบิล")
    try:
        return edit_receipt_amount(db, receipt, actor, body.new_amount, body.reason)
    except EvidenceError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/drops/{drop_id}/tarp", response_model=DropOut)
def upload_tarp_ep(
    body: TarpUploadRequest,
    drop: Drop = Depends(get_drop),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """อัปรูปผ้าใบรายจุด (Driver เจ้าของทริป) — บังคับแนบรูปจริง (Base64) เก็บเป็น URL"""
    _assert_own_driver(drop, user)
    try:
        return upload_tarp(db, drop, user, photo_b64=body.photo_b64)
    except (EvidenceError, StorageError) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/drops/{drop_id}/delivery", response_model=DropOut)
def record_delivery_ep(
    body: DeliveryRequest,
    drop: Drop = Depends(get_drop),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """รูปส่งของสำเร็จรายจุด (Driver เจ้าของทริป) → mark delivered + GPS ปลายทาง

    บังคับแนบรูปจริง — เก็บ URL ไฟล์ลง DB (ไม่มี marker "attached" แล้ว)
    """
    _assert_own_driver(drop, user)
    try:
        return record_delivery(
            db, drop, drop.trip.driver, body.lat, body.lng,
            captured_at=body.captured_at, photo_b64=body.photo_b64,
        )
    except (TransitionError, StorageError) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
