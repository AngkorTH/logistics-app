"""Router: Vehicle Assignment — จัดการทะเบียนรถ + ผูกคนขับประจำรถ (Admin+)

⚠️ Driver เข้าถึงไม่ได้ — ใช้ require_admin ทุก endpoint
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.models import User, Vehicle
from app.schemas.management import (
    VehicleAssignRequest,
    VehicleCreate,
    VehicleStatusRequest,
    VehicleUpdate,
)
from app.schemas.ops import VehicleOut
from app.services.management import (
    ManageError,
    assign_vehicle,
    create_vehicle,
    set_vehicle_status,
    update_vehicle,
)

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


def _get_vehicle(vehicle_id: int, db: Session) -> Vehicle:
    v = db.get(Vehicle, vehicle_id)
    if not v:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบทะเบียนรถ")
    return v


@router.get("", response_model=list[VehicleOut])
def list_vehicles(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """ทะเบียนรถทั้งหมด (Admin+)"""
    return db.query(Vehicle).order_by(Vehicle.plate).all()


@router.post("", response_model=VehicleOut)
def add_vehicle(
    body: VehicleCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    """เพิ่มทะเบียนรถใหม่ (Admin+)"""
    try:
        return create_vehicle(db, actor, body.plate, body.model, body.std_km_l)
    except ManageError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.patch("/{vehicle_id}", response_model=VehicleOut)
def edit_vehicle(
    vehicle_id: int,
    body: VehicleUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    """แก้ข้อมูลรถ (รุ่น/อัตราสิ้นเปลือง) (Admin+)"""
    vehicle = _get_vehicle(vehicle_id, db)
    return update_vehicle(db, vehicle, actor, body.model_dump(exclude_unset=True))


@router.post("/{vehicle_id}/status", response_model=VehicleOut)
def set_status(
    vehicle_id: int,
    body: VehicleStatusRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    """แจ้งรถเข้าซ่อม / ปลดล็อกกลับมาใช้งาน — **Admin ขึ้นไปเท่านั้น**

    ⚠️ Supervisor กดไม่ได้ (require_admin) — คนคุมงานทำได้แค่ "ปิดเหตุ" ที่คนขับแจ้งมา
    """
    vehicle = _get_vehicle(vehicle_id, db)
    try:
        return set_vehicle_status(db, vehicle, actor, body.status, body.reason)
    except ManageError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/{vehicle_id}/assign", response_model=VehicleOut)
def assign_driver(
    vehicle_id: int,
    body: VehicleAssignRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    """ผูก/ถอดคนขับประจำรถ (Admin+) — driver_id=null เพื่อถอด"""
    vehicle = _get_vehicle(vehicle_id, db)
    try:
        return assign_vehicle(db, vehicle, actor, body.driver_id)
    except ManageError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
