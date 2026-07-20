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
from app.models.enums import TripStatus, VehicleStatus, compute_allowance
from app.schemas.auth import UserOut
from app.schemas.ops import (
    AssignRequest,
    CompleteTripRequest,
    DriverPickOut,
    DropAddRequest,
    DropOut,
    EndTripRequest,
    FinanceOut,
    FuelLogRequest,
    ReceiptOut,
    StartTripRequest,
    GeoRequest,
    StatusOverrideRequest,
    TripAdjustRequest,
    TripCreate,
    TripDetailOut,
    TripOut,
    TripReceiptRequest,
    TripSummaryOut,
    UnfreezeRequest,
    VehicleOut,
)
from app.services.audit import who_label, write_audit
from app.services.finance import FinanceError, compute_finance, trip_summary
from app.services.trip_edit import adjust_trip
from app.services.evidence import EvidenceError, log_fuel, log_trip_receipt
from app.services.storage import StorageError
from app.services.state_machine import (
    TransitionError,
    TransitionWarning,
    add_drop,
    assign_trip,
    close_trip,
    complete_trip,
    end_trip,
    finish_loading,
    override_status,
    unfreeze_trip,
)

router = APIRouter(prefix="/trips", tags=["trips"])


def _detail(trip: Trip) -> TripDetailOut:
    """ประกอบทริป + สรุปการเงิน + สรุปรวบยอดทั้งเที่ยว เป็น response ก้อนเดียว"""
    fin = compute_finance(trip)
    base = TripOut.model_validate(trip, from_attributes=True)
    return TripDetailOut(
        **base.model_dump(),
        finance=FinanceOut(**fin.__dict__),
        summary=TripSummaryOut(**trip_summary(trip)),
    )


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
        # เบี้ยเลี้ยงคิดจากสูตร: รายได้ต่อขา × เปอร์เซ็นต์ความยาก (ไม่รับยอดจากผู้ใช้)
        diff = d.difficulty or trip.difficulty
        db.add(Drop(
            trip_id=trip.id, seq=i, name=d.label(),
            origin=d.origin.strip(), destination=d.destination.strip(),
            revenue=d.revenue, difficulty=diff,
            allowance=compute_allowance(d.revenue, diff),
        ))
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
    """รายชื่อคนขับที่ active ทั้งหมด — ใช้เป็น lookup ชื่อ (ประวัติทริป / คลังรถยนต์)
    ฟอร์มจ่ายงานใช้ /meta/drivers/available แทน (กรองเฉพาะคนรองาน)"""
    return (
        db.query(User)
        .filter(User.role == Role.DRIVER, User.active.is_(True))
        .order_by(User.emp_id)
        .all()
    )


@router.get("/meta/drivers/available", response_model=list[DriverPickOut])
def list_available_drivers(
    db: Session = Depends(get_db),
    _: User = Depends(require_supervisor),
):
    """รายชื่อคนขับสำหรับฟอร์มจ่ายงาน — **เฉพาะคนที่ 'รองาน' (สีขาว) เท่านั้น**

    คนที่กำลังวิ่งงาน (มีทริปสถานะ ORANGE/GREEN) ถูกตัดออก ไม่ส่งมาให้เลือก

    คนที่ว่างถูกแยก 2 ประเภทด้วย waiting_type:
    - SUB_TRIP = ยังมีเที่ยวหลักค้าง (completed_at ว่าง) → รับ "งานย่อย" เข้าเที่ยวเดิมได้
    - NEW_TRIP = ไม่มีเที่ยวหลักค้างเลย → พร้อมรับเที่ยวใหม่
    """
    drivers = (
        db.query(User)
        .filter(User.role == Role.DRIVER, User.active.is_(True))
        .order_by(User.emp_id)
        .all()
    )

    # ทริปที่ "ยังไม่จบ" ทั้งหมด (ยังไม่กดจบเที่ยว + ยังไม่ถูกล็อกการเงิน) ดึงรอบเดียวกัน N+1 query
    open_trips = (
        db.query(Trip)
        .filter(Trip.completed_at.is_(None), Trip.frozen.is_(False))
        .order_by(Trip.id)
        .all()
    )
    busy_ids = {t.driver_id for t in open_trips if t.status in (TripStatus.ORANGE, TripStatus.GREEN)}
    # เที่ยวหลักที่ยัง Active ของคนที่ว่าง — ต้องเคยถูกจ่ายงานแล้ว (มี assigned_at) ไม่ใช่ทริปเปล่า
    active_by_driver: dict[int, Trip] = {}
    for t in open_trips:
        if t.driver_id not in busy_ids and t.assigned_at is not None:
            active_by_driver.setdefault(t.driver_id, t)

    rows = []
    for d in drivers:
        if d.id in busy_ids:
            continue  # กำลังวิ่งงานอยู่ — ห้ามส่งไปให้เลือก
        act = active_by_driver.get(d.id)
        rows.append(DriverPickOut(
            id=d.id, emp_id=d.emp_id, name=d.name, phone=d.phone,
            role=d.role, active=d.active, notif=d.notif,
            waiting_type="SUB_TRIP" if act else "NEW_TRIP",
            active_trip_id=act.id if act else None,
            active_trip_code=act.code if act else None,
            active_trip_drops=len(act.drops) if act else 0,
        ))
    return rows


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
    """แท็บ 'รอตรวจ' (ข้อ 2.2 — Supervisor+): ทริปที่คนคุมงานกด 'จบเที่ยว' แล้ว
    แต่ยังไม่ถูกล็อกการเงิน — เรียงเก่า→ใหม่ · กดยืนยัน = เรียก /close เดิม
    แล้วทริปจะย้ายเข้า 'ประวัติทริป' (frozen)"""
    return (
        db.query(Trip)
        .filter(Trip.completed_at.isnot(None), Trip.frozen.is_(False))
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
    # รถกำลังซ่อม (คนขับแจ้งเหตุรถมีปัญหา) → ล็อกจ่ายงาน จนกว่าจะปิดเหตุ
    if vehicle.status is VehicleStatus.MAINTENANCE:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"รถ {vehicle.plate} กำลังซ่อม (คนขับแจ้งเหตุรถมีปัญหา) — จ่ายงานไม่ได้จนกว่าจะปิดเหตุ",
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
    body: StartTripRequest,
    trip: Trip = Depends(get_trip),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """คนขับกด 'ขนของขึ้นเสร็จ' (เจ้าของทริป) → GREEN + GPS ต้นทาง

    บังคับ:
    - เลขไมล์เริ่ม + รูปหน้าปัดไมล์ (ขาด/เลขน้อยกว่าเที่ยวก่อน = 400 บล็อก)
    - **รูปของที่ขนขึ้นรถ** (loaded_photo_b64) — ขาด = 422 ตั้งแต่ schema
      เก็บลงขาปัจจุบัน (Drop.loaded_photo) เป็น URL ไฟล์จริง
    """
    _assert_own_driver(trip, user)
    try:
        finish_loading(
            db, trip, trip.driver, body.lat, body.lng,
            odometer_start=body.odometer_start, odometer_photo_b64=body.odometer_photo_b64,
            loaded_photo_b64=body.loaded_photo_b64,
            force=body.force, captured_at=body.captured_at,
        )
    except TransitionWarning as w:
        raise HTTPException(status.HTTP_409_CONFLICT, str(w))
    except TransitionError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return _detail(trip)


@router.post("/{trip_id}/fuel", response_model=ReceiptOut)
def log_fuel_ep(
    body: FuelLogRequest,
    trip: Trip = Depends(get_trip),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """คนขับแจ้งเติมน้ำมันระหว่างทริป: รูปสลิป + จำนวนลิตร → Receipt draft ผูกกับทริป
    เติมได้หลายครั้งต่อทริป · ลิตรทุกใบจะถูกรวมตอนจบงานเพื่อคิด km/L"""
    _assert_own_driver(trip, user)
    try:
        return log_fuel(
            db, trip, user,
            liters=body.liters, photo_b64=body.photo_b64,
            captured_at=body.captured_at,
        )
    except (EvidenceError, StorageError) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/{trip_id}/receipt", response_model=ReceiptOut)
def log_trip_receipt_ep(
    body: TripReceiptRequest,
    trip: Trip = Depends(get_trip),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """อัปบิลระหว่างทาง (Mid-Trip) — น้ำมัน/ทางหลวง อัปกี่ใบก็ได้

    เปิดใช้ได้ตลอดที่คนขับยังวิ่งงาน (🟠 ไปขึ้นของ · 🟢 กำลังไปส่ง) ไม่ผูกกับ
    flow ส่งของเสร็จอีกแล้ว — แวะปั๊มก็ถ่ายส่งได้เลย
    ทริปที่ล็อกการเงินแล้ว/ยังไม่ถูกจ่ายงาน → 400
    """
    _assert_own_driver(trip, user)
    if trip.status not in (TripStatus.ORANGE, TripStatus.GREEN):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"อัปบิลระหว่างทางได้เฉพาะตอนกำลังวิ่งงาน (🟠/🟢) — ทริปนี้อยู่สถานะ {trip.status.value}",
        )
    try:
        return log_trip_receipt(
            db, trip, user, body.kind,
            photo_b64=body.photo_b64, liters=body.liters, captured_at=body.captured_at,
        )
    except (EvidenceError, StorageError) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/{trip_id}/end", response_model=TripDetailOut)
def end_trip_ep(
    body: EndTripRequest,
    trip: Trip = Depends(get_trip),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """จบงาน (End Trip): ส่งเลขไมล์จบ + **รูปหน้าปัดไมล์ (บังคับ)**
    → คิดระยะทาง + km/L อัตโนมัติแล้วเก็บลงทริป พร้อม URL รูปหน้าปัด
    ยังส่งของไม่ครบ → 409 ให้ยืนยันแล้วส่ง force=True (warn-don't-block)"""
    _assert_own_driver(trip, user)
    try:
        end_trip(
            db, trip, user, body.odometer_end,
            odometer_photo_b64=body.odometer_photo_b64, force=body.force,
        )
    except TransitionWarning as w:
        raise HTTPException(status.HTTP_409_CONFLICT, str(w))
    except (TransitionError, StorageError) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return _detail(trip)


@router.post("/{trip_id}/drops", response_model=DropOut)
def add_drop_ep(
    body: DropAddRequest,
    trip: Trip = Depends(get_trip),
    db: Session = Depends(get_db),
    actor: User = Depends(require_supervisor),
):
    """เพิ่มงานย่อย (Sub-Trip) เข้าไปในทริปเดิมที่ยัง Active (Supervisor+)
    บังคับ origin (เริ่มจากไหน) + destination (ไปส่งที่ไหน) เสมอ"""
    try:
        return add_drop(
            db, trip, actor,
            origin=body.origin, destination=body.destination,
            name=body.name, revenue=body.revenue, difficulty=body.difficulty,
        )
    except TransitionError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/{trip_id}/complete", response_model=TripDetailOut)
def complete_ep(
    body: CompleteTripRequest | None = None,
    trip: Trip = Depends(get_trip),
    db: Session = Depends(get_db),
    actor: User = Depends(require_supervisor),
):
    """จบเที่ยวหลัก (Supervisor+) — เที่ยวจะจบสมบูรณ์ก็ต่อเมื่อกดปุ่มนี้เท่านั้น
    ยังส่งงานย่อยไม่ครบ → 409 ให้ยืนยันแล้วส่ง force=True"""
    try:
        complete_trip(db, trip, actor, force=bool(body and body.force))
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
