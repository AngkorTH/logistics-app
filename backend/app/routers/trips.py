"""Router: Trip read + State Machine transitions (3 สี White/Orange/Green)

- อ่านทริป: Driver เห็นเฉพาะของตัวเอง / Supervisor+ เห็นทุกทริป (ownership ผ่าน deps.get_trip)
- จ่ายงาน / ปิดงาน = Supervisor ขึ้นไป
- ขนของขึ้นเสร็จ = Driver เจ้าของทริป (soft-block ผ้าใบ)
- TransitionWarning (ข้ามลำดับ/รูปไม่ครบ) → HTTP 409 ให้ frontend เด้งยืนยันแล้วส่ง force=True
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_trip, require_supervisor
from app.models import Drop, Role, Trip, User, Vehicle
from app.schemas.auth import UserOut
from app.schemas.ops import (
    AssignRequest,
    FinanceOut,
    GeoRequest,
    StatusOverrideRequest,
    TripAdjustRequest,
    TripCreate,
    TripDetailOut,
    TripOut,
    UnfreezeRequest,
    VehicleOut,
)
from app.services.audit import who_label, write_audit
from app.services.finance import FinanceError, compute_finance
from app.services.trip_edit import adjust_trip
from app.services.state_machine import (
    TransitionError,
    TransitionWarning,
    assign_trip,
    close_trip,
    finish_loading,
    override_status,
    unfreeze_trip,
)

router = APIRouter(prefix="/trips", tags=["trips"])


def _detail(trip: Trip) -> TripDetailOut:
    """ประกอบทริป + สรุปการเงินเป็น response ก้อนเดียว"""
    fin = compute_finance(trip)
    base = TripOut.model_validate(trip, from_attributes=True)
    return TripDetailOut(**base.model_dump(), finance=FinanceOut(**fin.__dict__))


def _assert_own_driver(trip: Trip, user: User) -> None:
    """เฉพาะคนขับเจ้าของทริปเท่านั้นที่กดปุ่มฝั่ง Driver ได้ (กันคนขับกดแทนคนอื่น)"""
    if user.role is Role.DRIVER and trip.driver_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "ทำรายการได้เฉพาะทริปของตนเอง")


@router.get("", response_model=list[TripOut])
def list_trips(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """รายการทริป — Driver กรองเฉพาะของตัวเอง, Supervisor+ เห็นทั้งหมด"""
    q = db.query(Trip)
    if user.role is Role.DRIVER:
        q = q.filter(Trip.driver_id == user.id)
    return q.order_by(Trip.id).all()


@router.post("", response_model=TripOut)
def create_trip(
    body: TripCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_supervisor),
):
    """สร้างทริปใหม่ + จุดส่ง 1-5 จุด (Supervisor+) — สถานะเริ่มต้น WHITE รอจ่ายงาน"""
    driver = db.get(User, body.driver_id)
    if not driver or driver.role is not Role.DRIVER:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "driver_id ไม่ใช่พนักงานขับรถ")
    if not driver.active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "คนขับคนนี้ถูกระงับการใช้งาน")

    code = f"T-{db.query(Trip).count() + 1:03d}"
    trip = Trip(code=code, driver_id=driver.id, distance_km=body.distance_km)
    db.add(trip)
    db.flush()
    for i, d in enumerate(body.drops, start=1):
        db.add(Drop(trip_id=trip.id, seq=i, name=d.name.strip(), allowance=d.allowance))
    db.commit()
    db.refresh(trip)

    write_audit(
        db, who_label(actor), "สร้างทริป", trip.code,
        f"คนขับ {driver.emp_id} · {len(body.drops)} จุดส่ง",
    )
    return trip


@router.get("/meta/drivers", response_model=list[UserOut])
def list_drivers(
    db: Session = Depends(get_db),
    _: User = Depends(require_supervisor),
):
    """รายชื่อคนขับที่ active — ใช้ในฟอร์มจ่ายงาน"""
    return (
        db.query(User)
        .filter(User.role == Role.DRIVER, User.active.is_(True))
        .order_by(User.emp_id)
        .all()
    )


@router.get("/meta/vehicles", response_model=list[VehicleOut])
def list_vehicles(
    db: Session = Depends(get_db),
    _: User = Depends(require_supervisor),
):
    """ทะเบียนรถทั้งหมด — ใช้เลือกผูกทะเบียนตอนจ่ายงาน"""
    return db.query(Vehicle).order_by(Vehicle.plate).all()


@router.get("/pending-review", response_model=list[TripOut])
def pending_review(
    db: Session = Depends(get_db),
    _: User = Depends(require_supervisor),
):
    """แท็บ 'รอตรวจ' (ข้อ 2.2 — Supervisor+): ทริปที่คนขับส่งงานจบแล้ว (closed_at)
    แต่ยังไม่ถูกล็อกการเงิน — เรียงเก่า→ใหม่ · กดยืนยัน = เรียก /close เดิม
    แล้วทริปจะย้ายเข้า 'ประวัติทริป' (frozen)"""
    return (
        db.query(Trip)
        .filter(Trip.closed_at.isnot(None), Trip.frozen.is_(False))
        .order_by(Trip.closed_at.asc())
        .all()
    )


@router.get("/{trip_id}", response_model=TripDetailOut)
def get_trip_detail(trip: Trip = Depends(get_trip)):
    """รายละเอียดทริป + การเงิน (ownership เช็กแล้วใน get_trip)"""
    return _detail(trip)


@router.post("/{trip_id}/assign", response_model=TripDetailOut)
def assign(
    body: AssignRequest,
    trip: Trip = Depends(get_trip),
    db: Session = Depends(get_db),
    actor: User = Depends(require_supervisor),
):
    """จ่ายงาน (Supervisor+): ตั้งความยากทริป → ORANGE
    ทะเบียนรถดึงอัตโนมัติจากคลังรถยนต์ที่ผูกกับคนขับ (ข้อ 2.1) — ไม่มีช่องให้เลือกแล้ว"""
    vehicle = db.query(Vehicle).filter(Vehicle.driver_id == trip.driver_id).first()
    if not vehicle:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "คนขับคนนี้ยังไม่ถูกผูกรถในคลังรถยนต์ — ไปผูกรถที่หน้า 'คลังรถยนต์' ก่อนจ่ายงาน",
        )
    try:
        assign_trip(db, trip, vehicle.plate, actor, difficulty=body.difficulty, force=body.force)
    except TransitionWarning as w:
        raise HTTPException(status.HTTP_409_CONFLICT, str(w))
    except TransitionError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return _detail(trip)


@router.patch("/{trip_id}/adjust", response_model=TripDetailOut)
def adjust(
    body: TripAdjustRequest,
    trip: Trip = Depends(get_trip),
    db: Session = Depends(get_db),
    actor: User = Depends(require_supervisor),
):
    """แก้ข้อมูลทริป (Supervisor+/Admin): ระยะทาง/ความยาก/เบี้ยเลี้ยง/หักเงิน
    บังคับ edit_reason เสมอ (schema) → บันทึกลง Audit Trail
    """
    try:
        adjust_trip(db, trip, actor, body.model_dump(exclude_unset=True))
    except FinanceError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return _detail(trip)


@router.post("/{trip_id}/unfreeze", response_model=TripDetailOut)
def unfreeze(
    body: UnfreezeRequest,
    trip: Trip = Depends(get_trip),
    db: Session = Depends(get_db),
    actor: User = Depends(require_supervisor),
):
    """ปลดล็อกการเงิน (Supervisor/Admin) เพื่อกลับมาแก้ไข — บังคับเหตุผล + เด้งแจ้งเตือน"""
    try:
        unfreeze_trip(db, trip, actor, body.reason)
    except TransitionError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return _detail(trip)


@router.post("/{trip_id}/override-status", response_model=TripDetailOut)
def override_status_ep(
    body: StatusOverrideRequest,
    trip: Trip = Depends(get_trip),
    db: Session = Depends(get_db),
    actor: User = Depends(require_supervisor),
):
    """เปลี่ยนสถานะทริปแบบ Manual (Supervisor/Admin) — บังคับเหตุผล + แจ้งเตือนคนขับ (task 1)"""
    try:
        override_status(db, trip, actor, body.status, body.reason)
    except TransitionError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return _detail(trip)


@router.post("/{trip_id}/finish-loading", response_model=TripDetailOut)
def finish_loading_ep(
    body: GeoRequest,
    trip: Trip = Depends(get_trip),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """คนขับกด 'ขนของขึ้นเสร็จ' (เจ้าของทริป) → GREEN + GPS ต้นทาง"""
    _assert_own_driver(trip, user)
    try:
        finish_loading(
            db, trip, trip.driver, body.lat, body.lng,
            force=body.force, captured_at=body.captured_at,
        )
    except TransitionWarning as w:
        raise HTTPException(status.HTTP_409_CONFLICT, str(w))
    except TransitionError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return _detail(trip)


@router.post("/{trip_id}/close", response_model=TripDetailOut)
def close(
    body: GeoRequest | None = None,
    trip: Trip = Depends(get_trip),
    db: Session = Depends(get_db),
    actor: User = Depends(require_supervisor),
):
    """ปิดงาน (Supervisor+): → WHITE + freeze การเงินถาวร"""
    force = bool(body and body.force)
    try:
        close_trip(db, trip, actor, force=force)
    except TransitionWarning as w:
        raise HTTPException(status.HTTP_409_CONFLICT, str(w))
    except TransitionError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return _detail(trip)
