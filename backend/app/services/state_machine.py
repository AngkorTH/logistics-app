"""State Machine รถ 3 สี (White → Orange → Green → White) + GPS Geofencing

ตรรกะหัวใจของ Step 2 ตาม skill.md ข้อ 2 และ 4:

    WHITE (รองาน)  --assign+bind รถ (Supervisor)-->  ORANGE (ขึ้นของ)
    ORANGE         --"ขนของขึ้นเสร็จ" (Driver)-->     GREEN  (กำลังส่ง)
    GREEN          --"ปิดงาน" (Supervisor)-->          WHITE  (จบงาน/freeze)

ปรัชญาการ์ด (สำคัญมาก — พลาดง่าย):
- **Soft-block:** การกด "ขนของขึ้นเสร็จ" ไป GREEN ทำได้แม้ยังไม่อัปโหลดรูปผ้าใบ — ห้าม hard-block
- **Warn-don't-block:** ถ้า Supervisor สั่งข้ามลำดับ (เช่น กระโดดไป GREEN ตรงๆ)
  หรือปิดงานทั้งที่ยังส่งรูปไม่ครบ → เตือนให้ยืนยัน (raise TransitionWarning)
  แต่ถ้ายืนยันแล้ว (force=True) ให้ทำได้ พร้อมทำเครื่องหมาย override ไว้

GPS Geofencing บันทึกอัตโนมัติ 2 จังหวะ:
- กด "ขนของขึ้นเสร็จ" → event LOADED (ตรวจพิกัดต้นทาง)
- อัปโหลดรูปส่งสำเร็จรายจุด → event DELIVERED (ตรวจพิกัดปลายทาง)
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Drop, GpsLog, Trip, User
from app.models.enums import (
    ALLOWANCE_RATE,
    GpsEvent,
    TripDifficulty,
    TripStatus,
    compute_allowance,
)
from app.services.audit import who_label, write_audit
from app.services.notification import push_notification


class TransitionError(Exception):
    """การเปลี่ยนสถานะที่ห้ามเด็ดขาด (hard-block) — เช่นข้อมูลไม่ครบจนทำต่อไม่ได้"""


class TransitionWarning(Exception):
    """การเปลี่ยนสถานะที่ 'ผิดปกติแต่ทำได้' — ต้องให้ผู้ใช้ยืนยันก่อน (force=True)

    ตัวเรียกใช้ (router) ควรแปลงเป็น HTTP 409 พร้อมข้อความ เพื่อให้ frontend
    เด้ง popup ยืนยัน แล้วเรียกซ้ำด้วย force=True
    """


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _assert_not_paused(trip: Trip) -> None:
    """ทริปที่มีเหตุฉุกเฉิน (SOS) ค้างอยู่ถูกล็อกสถานะชั่วคราว — ห้ามเดินหน้า
    จนกว่าคุมงาน/แอดมินจะปิดเหตุ (ข้อ 1.4) · override_status ยังใช้ได้เป็นทางหนีฉุกเฉิน"""
    if trip.paused:
        raise TransitionError(
            f"ทริป {trip.code} ถูกพักชั่วคราวจากเหตุฉุกเฉิน (SOS) — "
            "ต้องให้คนคุมงาน/แอดมินปิดเหตุก่อนจึงจะทำรายการต่อได้"
        )


def unfreeze_trip(db: Session, trip: Trip, actor: User, reason: str) -> Trip:
    """ปลดล็อกการเงิน (unfreeze) เพื่อกลับมาแก้ไขทริปที่ปิดบัญชีแล้ว

    ต่างจาก correction workflow (ที่ต้องให้ Super Admin อนุมัติ): อันนี้ Supervisor/Admin
    ปลดล็อกได้เอง แต่ **บังคับเหตุผล + เด้งแจ้งเตือน** เพื่อให้ทีมรู้ว่ามีการแก้ของที่ล็อกไปแล้ว
    ทริปที่ freeze อยู่ = ดูได้อย่างเดียว จนกว่าจะปลดล็อกตรงนี้
    """
    if not reason or not reason.strip():
        raise TransitionError("ต้องระบุเหตุผลการปลดล็อกเสมอ")
    if not trip.frozen:
        raise TransitionError(f"ทริป {trip.code} ไม่ได้ถูกล็อกอยู่")

    trip.frozen = False
    trip.override = True  # ทำเครื่องหมายว่าทริปนี้เคยถูกปลดล็อกมาแก้
    db.commit()
    db.refresh(trip)

    write_audit(
        db, who_label(actor), "ปลดล็อกการเงิน", trip.code,
        f"ปลด freeze เพื่อแก้ไขข้อมูล · เหตุผล: {reason.strip()}",
    )
    push_notification(
        db, "TRIP_UNFROZEN", f"ปลดล็อกการเงิน · {trip.code}",
        f"{who_label(actor)} ปลดล็อกทริปเพื่อแก้ไข · เหตุผล: {reason.strip()}", trip.id,
    )
    return trip


def _notify_status_change(trip: Trip, actor: User, old: TripStatus, new: TripStatus) -> None:
    """แจ้งเตือนคนขับว่าสถานะถูกเปลี่ยนแบบ Manual โดยใคร (stub — ต่อ push จริงภายหลัง)"""
    driver = trip.driver
    if driver and driver.notif:
        print(
            f"[PUSH->{driver.emp_id}] สถานะทริป {trip.code} ถูกเปลี่ยน "
            f"{old.value} -> {new.value} โดย {who_label(actor)}"
        )


def override_status(
    db: Session, trip: Trip, actor: User, new_status: TripStatus, reason: str
) -> Trip:
    """เปลี่ยนสถานะทริปแบบ Manual (Supervisor/Admin) — บังคับเหตุผล + แจ้งเตือนคนขับ (task 1)

    ต่างจาก assign/finish/close ปกติ: กดตั้งสถานะเป้าหมายได้ตรงๆ (override ลำดับ)
    ใช้กรณีข้อมูลจริงไม่ตรง เช่นคนขับลืมกดปุ่ม — คนคุมงานปรับให้ถูกต้อง
    """
    if not reason or not reason.strip():
        raise TransitionError("ต้องระบุเหตุผลการเปลี่ยนสถานะเสมอ")
    if trip.frozen:
        raise TransitionError(f"ทริป {trip.code} ถูกล็อกการเงินแล้ว — เปลี่ยนสถานะไม่ได้")

    old = trip.status
    if new_status is old:
        raise TransitionError(f"ทริป {trip.code} อยู่สถานะ {old.value} อยู่แล้ว")

    trip.status = new_status
    trip.override = True  # ทำเครื่องหมายว่าสถานะนี้มาจากการ override ด้วยมือ
    # เติม timestamp ที่จำเป็นถ้าเลื่อนไปข้างหน้าแล้วยังว่าง (ให้ dispatch metric คิดต่อได้)
    if new_status is TripStatus.ORANGE and trip.assigned_at is None:
        trip.assigned_at = _now()
    if new_status is TripStatus.GREEN and trip.finished_loading_at is None:
        trip.finished_loading_at = _now()
    if new_status is TripStatus.WHITE:
        trip.closed_at = trip.closed_at or _now()
    db.commit()
    db.refresh(trip)

    write_audit(
        db, who_label(actor), "เปลี่ยนสถานะ (Manual Override)", trip.code,
        f"{old.value} -> {new_status.value} · เหตุผล: {reason.strip()}",
    )
    _notify_status_change(trip, actor, old, new_status)
    return trip


def _notify_tarpaulin(driver: User, moment: str) -> None:
    """ส่ง push เตือนคลุมผ้าใบ (stub) — ยิงตอนจ่ายงาน และตอนสถานะเป็น GREEN

    ตอนนี้ยังเป็น stub (print) — จะต่อ push service จริงภายหลัง
    """
    if driver.notif:
        print(f"[PUSH→{driver.emp_id}] อย่าลืมคลุมผ้าใบ! ({moment})")


# ---------------------------------------------------------------------------
# WHITE → ORANGE : Supervisor จ่ายงาน + ผูกทะเบียนรถ
# ---------------------------------------------------------------------------
def assign_trip(
    db: Session,
    trip: Trip,
    plate: str,
    actor: User,
    *,
    difficulty: TripDifficulty | None = None,
    force: bool = False,
) -> Trip:
    """จ่ายงาน: ผูกทะเบียนรถ + ตั้งความยากทริป แล้วดันสถานะเป็น ORANGE อัตโนมัติ

    การ์ด: ปกติต้องมาจาก WHITE เท่านั้น ถ้าทริปไม่ได้อยู่ WHITE (เช่นกำลังวิ่งอยู่)
    ถือเป็นการข้ามลำดับ → เตือนให้ยืนยัน
    """
    if not plate or not plate.strip():
        raise TransitionError("ต้องระบุทะเบียนรถก่อนจ่ายงาน")

    # กันคนขับมีงานค้างหลายใบ: 1 คนขับ = 1 งานที่กำลังวิ่ง (ORANGE/GREEN) เท่านั้น
    # ถ้าไม่กัน ทริปเก่าค้างจะทำให้คนขับไม่มีวันกลับสถานะ 'รองาน' ในคิว (state mismatch)
    active_other = (
        db.query(Trip)
        .filter(
            Trip.driver_id == trip.driver_id,
            Trip.id != trip.id,
            Trip.status.in_([TripStatus.ORANGE, TripStatus.GREEN]),
        )
        .first()
    )
    if active_other and not force:
        raise TransitionWarning(
            f"คนขับมีงาน {active_other.code} ที่ยังไม่จบ (สถานะ {active_other.status.value}) "
            "— จ่ายงานใหม่ซ้ำหรือไม่?"
        )

    if trip.status is not TripStatus.WHITE and not force:
        raise TransitionWarning(
            f"ทริป {trip.code} ไม่ได้อยู่สถานะ 'รองาน' (ปัจจุบัน {trip.status.value}) "
            "— การจ่ายงานซ้ำจะข้ามลำดับปกติ ยืนยันหรือไม่?"
        )

    skipped = trip.status is not TripStatus.WHITE
    trip.plate = plate.strip()
    if difficulty is not None:
        trip.difficulty = difficulty
    trip.status = TripStatus.ORANGE
    trip.assigned_at = _now()
    if skipped:
        trip.override = True
    db.commit()
    db.refresh(trip)

    write_audit(
        db, who_label(actor), "จ่ายงาน", trip.code,
        f"ผูกทะเบียน {trip.plate} · → ORANGE" + (" · ข้ามลำดับ (override)" if skipped else ""),
    )
    _notify_tarpaulin(trip.driver, "ตอนรับงาน")
    return trip


def _last_odometer_end(db: Session, trip: Trip) -> float | None:
    """เลขไมล์จบล่าสุดของคนขับคนนี้ (ทริปอื่นที่ปิดงานแล้วและมีเลขไมล์จบ)"""
    prev = (
        db.query(Trip)
        .filter(
            Trip.driver_id == trip.driver_id,
            Trip.id != trip.id,
            Trip.odometer_end.isnot(None),
        )
        .order_by(Trip.odometer_end.desc())
        .first()
    )
    return prev.odometer_end if prev else None


def _validate_odometer_start(
    db: Session, trip: Trip, odometer_start: float | None, photo_b64: str | None
) -> tuple[float, str]:
    """ด่านบังคับก่อนเริ่มงาน: ต้องมีเลขไมล์ + รูปหน้าปัดไมล์ และเลขต้องสมเหตุสมผล

    คืน (เลขไมล์ที่ปัดแล้ว, URL รูปที่บันทึก) · ผิดเงื่อนไขข้อใดข้อหนึ่ง = TransitionError
    """
    from app.services.storage import StorageError, save_photo_b64

    if odometer_start is None:
        raise TransitionError("ต้องกรอกเลขไมล์ตอนเริ่มงานก่อนจึงจะเริ่มงานได้")
    if odometer_start < 0:
        raise TransitionError("เลขไมล์ตอนเริ่มงานติดลบไม่ได้")
    if not photo_b64 or not photo_b64.strip():
        raise TransitionError("ต้องถ่ายรูปหน้าปัดไมล์แนบมาด้วยก่อนเริ่มงาน")

    last = _last_odometer_end(db, trip)
    if last is not None and odometer_start < last:
        raise TransitionError(
            f"เลขไมล์เริ่ม ({odometer_start:.1f}) น้อยกว่าเลขไมล์จบของเที่ยวก่อนหน้า "
            f"({last:.1f}) — ตรวจสอบเลขบนหน้าปัดอีกครั้ง"
        )

    try:
        path = save_photo_b64(photo_b64, "odo")
    except StorageError as e:
        raise TransitionError(f"รูปหน้าปัดไมล์ใช้ไม่ได้: {e}")
    if not path:
        raise TransitionError("ต้องถ่ายรูปหน้าปัดไมล์แนบมาด้วยก่อนเริ่มงาน")
    return round(float(odometer_start), 1), path


# ---------------------------------------------------------------------------
# ORANGE → GREEN : Driver กด "ขนของขึ้นเสร็จ" + GPS ต้นทาง
# ---------------------------------------------------------------------------
def finish_loading(
    db: Session,
    trip: Trip,
    driver: User,
    lat: float,
    lng: float,
    *,
    # เลขไมล์เริ่ม + รูปหน้าปัดปกติถูกบันทึกไปแล้วตอน "ส่งผลตรวจสภาพรถ"
    # ส่งซ้ำตรงนี้ได้ (เช่นข้อมูลเก่า/แก้ไข) — ไม่ส่ง = ใช้ค่าที่บันทึกไว้ในทริป
    odometer_start: float | None = None,
    odometer_photo_b64: str | None = None,
    force: bool = False,
    captured_at: datetime | None = None,  # เวลากดจริง (Offline Auto-Sync) — None = ตอนนี้
) -> Trip:
    """คนขับกด 'ขนของขึ้นเสร็จ' → GREEN พร้อม geo-stamp ต้นทาง (LOADED)

    - Soft-block ผ้าใบ: ไม่เช็ครูปผ้าใบเลย ปล่อยให้ไป GREEN ได้เสมอ
    - Idempotency: กดซ้ำ (already GREEN) จะไม่สร้าง GPS log ซ้ำ
    - การ์ดลำดับ: ปกติต้องมาจาก ORANGE ถ้าไม่ใช่ (เช่นยังไม่ถูกจ่ายงาน) → เตือนให้ยืนยัน
    - **Hard-block เลขไมล์:** ต้องส่งทั้งเลขไมล์เริ่ม + รูปหน้าปัดไมล์ และเลขต้องไม่น้อยกว่า
      เลขไมล์จบของเที่ยวก่อนหน้าของคนขับคนนี้ (ข้อมูลผิดแน่นอน = ห้ามเริ่มงาน)
    """
    # กันกดซ้ำ (double-tap) — ถ้าเป็น GREEN อยู่แล้วและ stamp ต้นทางไปแล้ว คืนค่าเดิม
    if trip.status is TripStatus.GREEN and trip.finished_loading_at is not None:
        return trip

    _assert_not_paused(trip)  # มีเหตุ SOS ค้าง → ล็อกทุกการเดินหน้า

    # ด่านตรวจสภาพรถก่อนวิ่ง (Pre-trip Inspection) — hard-block ตามที่ผู้ใช้ยืนยัน:
    # ต้อง PASSED หรือ APPROVED ก่อนเท่านั้น (มีจุดชำรุดรอประเมิน = ปุ่มถูกล็อก)
    # import ในฟังก์ชันเพื่อเลี่ยง circular import
    from app.services.inspection import inspection_ready

    if trip.status is TripStatus.ORANGE and not inspection_ready(db, trip):
        raise TransitionError(
            "ต้องตรวจสภาพรถก่อนวิ่ง (Pre-trip Inspection) ให้ผ่านก่อน "
            "จึงจะกด 'ขนของขึ้นเสร็จ' ได้"
        )

    # ---- ด่านเลขไมล์เริ่มงาน (Odometer Start Tracking) — hard-block ทุกกรณี ----
    if odometer_start is None and odometer_photo_b64 is None:
        # ใช้ค่าที่บันทึกตอนส่งผลตรวจสภาพรถ — ถ้ายังไม่มีแปลว่ายังไม่ผ่านด่านนั้น
        if trip.odometer_start is None or not trip.odometer_start_photo:
            raise TransitionError(
                "ยังไม่มีเลขไมล์เริ่ม/รูปหน้าปัดไมล์ของทริปนี้ — "
                "ต้องกรอกตอนส่งผลตรวจสภาพรถก่อนวิ่งก่อน"
            )
        odo, photo_path = trip.odometer_start, trip.odometer_start_photo
    else:
        odo, photo_path = _validate_odometer_start(db, trip, odometer_start, odometer_photo_b64)

    if trip.status is not TripStatus.ORANGE and not force:
        raise TransitionWarning(
            f"ทริป {trip.code} ยังไม่อยู่สถานะ 'ขึ้นของ' (ปัจจุบัน {trip.status.value}) "
            "— การกดขนของเสร็จตอนนี้จะข้ามลำดับปกติ ยืนยันหรือไม่?"
        )

    skipped = trip.status is not TripStatus.ORANGE
    trip.odometer_start = odo
    trip.odometer_start_photo = photo_path
    trip.status = TripStatus.GREEN
    trip.finished_loading_at = captured_at or _now()
    if skipped:
        trip.override = True

    # GPS Geofencing ต้นทาง — drop_id เป็น null เพราะเป็นจุดขึ้นของ ไม่ใช่จุดส่ง
    db.add(GpsLog(
        trip_id=trip.id, drop_id=None, event=GpsEvent.LOADED, lat=lat, lng=lng,
        recorded_at=captured_at or _now(),
    ))
    db.commit()
    db.refresh(trip)

    write_audit(
        db, who_label(driver), "ขนของขึ้นเสร็จ", trip.code,
        f"→ GREEN · GPS ต้นทาง {lat:.5f},{lng:.5f} · เลขไมล์เริ่ม {trip.odometer_start:.1f} (แนบรูปหน้าปัด)"
        + (" · ข้ามลำดับ (override)" if skipped else ""),
    )
    _notify_tarpaulin(driver, "สถานะเป็นสีเขียว")
    return trip


# ---------------------------------------------------------------------------
# จุดส่งย่อย : อัปโหลดรูปส่งสำเร็จ + GPS ปลายทาง (สถานะยังเป็น GREEN)
# ---------------------------------------------------------------------------
def record_delivery(
    db: Session, drop: Drop, driver: User, lat: float, lng: float,
    *,
    captured_at: datetime | None = None,  # เวลากดจริง (Offline Auto-Sync) — None = ตอนนี้
    photo_b64: str | None = None,         # รูปส่งของสำเร็จ (Phase 4) — เก็บไฟล์จริง
) -> Drop:
    """คนขับส่งของสำเร็จ 1 จุด: ทำเครื่องหมายส่งแล้ว + รูป + geo-stamp ปลายทาง (DELIVERED)

    Dynamic Multi-Drop: จบงานย่อย = คนขับกลับเป็น **รองาน (WHITE) ทันที** เพื่อรับงานย่อยใบถัดไป
    ได้เลย แต่ **เที่ยวหลักยัง Active** (completed_at ยังว่าง) — จบเที่ยวจริงต้องให้ Supervisor
    กด "จบเที่ยว" (complete_trip) เท่านั้น
    Idempotency: ถ้าจุดนี้ delivered ไปแล้ว ไม่สร้าง GPS log ซ้ำ
    """
    trip = drop.trip
    # กดซ้ำ (double-tap) → คืนค่าเดิมเงียบๆ ต้องเช็คก่อนการ์ดสถานะ
    # เพราะพอส่งขาสำเร็จ ทริปจะพลิกเป็น WHITE ทันที การกดซ้ำจึงไม่ควรกลายเป็น error
    if drop.delivered:
        return drop

    # 1 ขาต่อครั้ง: ส่งของได้เฉพาะตอนกำลังวิ่ง (GREEN) เท่านั้น
    # จบขาแล้วคนขับกลับเป็น WHITE และ **ไปขาถัดไปเองไม่ได้** จนกว่าคนคุมงานจะจ่ายงานย่อยใหม่
    if trip.status is not TripStatus.GREEN:
        raise TransitionError(
            f"ยังส่งของจุด {drop.seq} ไม่ได้ — ต้องรอคนคุมงานจ่ายงานย่อยนี้ก่อน "
            f"(ทริปต้องอยู่สถานะ GREEN · ปัจจุบัน {trip.status.value})"
        )

    _assert_not_paused(trip)  # มีเหตุ SOS ค้าง → ล็อกทุกการเดินหน้า

    # Phase 4: เก็บรูปจริงถ้าส่งมา — ไม่ส่ง = "attached" (นับว่ามีหลักฐานเหมือน flow เดิม)
    from app.services.storage import save_photo_b64

    coord = f"{lat:.5f},{lng:.5f}"
    drop.delivered = True
    drop.photo = save_photo_b64(photo_b64, "dlv") or "attached"
    drop.gps = coord
    drop.delivered_at = captured_at or _now()
    # จบงานย่อย → คนขับว่างทันที (รองาน/สีขาว) · เที่ยวหลักไม่ถูกปิด
    trip.status = TripStatus.WHITE

    db.add(GpsLog(
        trip_id=trip.id, drop_id=drop.id, event=GpsEvent.DELIVERED, lat=lat, lng=lng,
        recorded_at=captured_at or _now(),
    ))
    db.commit()
    db.refresh(drop)

    write_audit(
        db, who_label(driver), "จบงานย่อย (ส่งของสำเร็จ)", trip.code,
        f"จุด {drop.seq} ({drop.origin or '—'} → {drop.destination or drop.name}) · "
        f"GPS ปลายทาง {coord} · คนขับ → รองาน (เที่ยวหลักยัง Active)",
    )

    # ส่งครบทุกงานย่อยแล้ว → แจ้งคนคุมงานให้มากด "จบเที่ยว" (ระบบไม่จบให้เอง)
    if trip.drops and all(d.delivered for d in trip.drops):
        push_notification(
            db, "TRIP_DONE", f"ทริป {trip.code} ส่งครบทุกงานย่อยแล้ว",
            "คนขับส่งของครบทุกจุด · รอคนคุมงานกด 'จบเที่ยว'", trip.id,
        )
    return drop


# ---------------------------------------------------------------------------
# จบเที่ยวหลัก (Complete Main Trip) : Supervisor เท่านั้น
# ---------------------------------------------------------------------------
def complete_trip(db: Session, trip: Trip, actor: User, *, force: bool = False) -> Trip:
    """Supervisor กด "จบเที่ยว" → เที่ยวหลักจบสมบูรณ์ (คำนวณเงิน/รอล็อกการเงิน)

    ก่อนหน้านี้เที่ยวหลักยัง Active ได้เรื่อยๆ แม้คนขับจะจบงานย่อยไปแล้วหลายใบ
    การ์ด:
    - จบเที่ยวไปแล้ว / freeze แล้ว → hard-block
    - ยังส่งงานย่อยไม่ครบ → เตือนให้ยืนยัน (warn-don't-block)
    """
    if trip.frozen:
        raise TransitionError(f"ทริป {trip.code} ถูกล็อกการเงินแล้ว")
    if trip.completed_at is not None:
        raise TransitionError(f"ทริป {trip.code} จบเที่ยวไปแล้ว")

    _assert_not_paused(trip)

    if not trip.drops:
        raise TransitionError(f"ทริป {trip.code} ยังไม่มีงานย่อย — จบเที่ยวไม่ได้")

    undelivered = [d.seq for d in trip.drops if not d.delivered]
    if undelivered and not force:
        raise TransitionWarning(
            f"ยังส่งงานย่อยไม่ครบ (เหลือจุด {undelivered}) — ยืนยันจบเที่ยวหรือไม่?"
        )

    trip.status = TripStatus.WHITE
    trip.completed_at = _now()
    trip.closed_at = trip.closed_at or trip.completed_at
    trip.km_per_liter = compute_km_per_liter(trip)
    if undelivered:
        trip.override = True
    db.commit()
    db.refresh(trip)

    write_audit(
        db, who_label(actor), "จบเที่ยว (Complete Main Trip)", trip.code,
        f"งานย่อย {len(trip.drops)} ใบ → จบเที่ยว (รอตรวจบิล/ล็อกการเงิน)"
        + (f" · override ยังส่งไม่ครบจุด {undelivered}" if undelivered else ""),
    )
    push_notification(
        db, "TRIP_DONE", f"ทริป {trip.code} จบเที่ยวแล้ว",
        f"{who_label(actor)} กดจบเที่ยว · รอตรวจบิลและล็อกการเงิน", trip.id,
    )
    return trip


def add_drop(
    db: Session, trip: Trip, actor: User, *,
    origin: str, destination: str, name: str = "",
    revenue: float = 0, difficulty: TripDifficulty | None = None,
) -> Drop:
    """เพิ่มงานย่อย (Sub-Trip) เข้าไปในทริปเดิมที่ยัง Active

    บังคับ ต้นทาง/ปลายทาง/รายได้ต่อขา · เบี้ยเลี้ยงคิดเอง = รายได้ × เปอร์เซ็นต์ความยาก
    """
    if trip.frozen:
        raise TransitionError(f"ทริป {trip.code} ถูกล็อกการเงินแล้ว — เพิ่มงานย่อยไม่ได้")
    if trip.completed_at is not None:
        raise TransitionError(f"ทริป {trip.code} จบเที่ยวไปแล้ว — เพิ่มงานย่อยไม่ได้")
    if not origin.strip() or not destination.strip():
        raise TransitionError("ต้องกรอกทั้งต้นทาง (เริ่มจากไหน) และปลายทาง (ไปส่งที่ไหน)")
    if len(trip.drops) >= 5:
        raise TransitionError("1 เที่ยวมีงานย่อยได้สูงสุด 5 ใบ")
    if revenue <= 0:
        raise TransitionError("ต้องกรอกรายได้ต่อขา (มากกว่า 0) เพื่อคิดเบี้ยเลี้ยง")

    diff = difficulty or trip.difficulty
    drop = Drop(
        trip_id=trip.id,
        seq=max((d.seq for d in trip.drops), default=0) + 1,
        name=name.strip() or f"{origin.strip()} → {destination.strip()}",
        origin=origin.strip(),
        destination=destination.strip(),
        revenue=revenue,
        difficulty=diff,
        allowance=compute_allowance(revenue, diff),
    )
    db.add(drop)
    db.commit()
    db.refresh(drop)
    db.refresh(trip)

    write_audit(
        db, who_label(actor), "เพิ่มงานย่อย (Sub-Trip)", trip.code,
        f"จุด {drop.seq}: {drop.origin} → {drop.destination} · รายได้ {drop.revenue:.2f} × "
        f"{ALLOWANCE_RATE[diff] * 100:.0f}% ({diff.value}) = เบี้ยเลี้ยง {drop.allowance:.2f}",
    )
    return drop


# ---------------------------------------------------------------------------
# จบงาน (End Trip) : คนขับส่งเลขไมล์จบ → คิดอัตราสิ้นเปลือง km/L
# ---------------------------------------------------------------------------
def compute_km_per_liter(trip: Trip) -> float | None:
    """คิดอัตราสิ้นเปลืองของทริป — ปัดทศนิยม 1 ตำแหน่ง

    ระยะทาง = odometer_end − odometer_start (ถ้าไม่มีเลขไมล์ ใช้ distance_km ที่บันทึกไว้)
    ลิตรรวม = ผลรวม liters ของบิลน้ำมันทุกใบในทริป
    ลิตรรวม = 0 → คืน None (กันหารด้วยศูนย์)
    """
    from app.services.finance import total_liters

    liters = total_liters(trip)
    if liters <= 0:
        return None

    if trip.odometer_end is not None and trip.odometer_start is not None:
        distance = trip.odometer_end - trip.odometer_start
    else:
        distance = trip.distance_km or 0.0
    if distance <= 0:
        return None
    return round(distance / liters, 1)


def end_trip(
    db: Session, trip: Trip, actor: User, odometer_end: float, *, force: bool = False
) -> Trip:
    """บันทึกเลขไมล์ปลายเที่ยว → คิดระยะทาง + km/L แล้วเก็บลงทริป (ไม่ปิดเที่ยว)

    การ์ด:
    - freeze แล้ว → ห้ามแก้เลขไมล์ (ต้องขอปลดล็อกก่อน)
    - เลขไมล์จบ < เลขไมล์เริ่ม → hard-block (ข้อมูลผิดแน่นอน)
    - ยังส่งของไม่ครบทุกจุด → เตือนให้ยืนยัน (warn-don't-block)
    """
    if trip.frozen:
        raise TransitionError(f"ทริป {trip.code} ถูกล็อกการเงินแล้ว — แก้เลขไมล์ไม่ได้ ต้องขอปลดล็อกก่อน")
    if odometer_end is None or odometer_end < 0:
        raise TransitionError("เลขไมล์จบต้องเป็นตัวเลขไม่ติดลบ")
    if trip.odometer_start is not None and odometer_end < trip.odometer_start:
        raise TransitionError(
            f"เลขไมล์จบ ({odometer_end:.1f}) น้อยกว่าเลขไมล์เริ่ม ({trip.odometer_start:.1f})"
        )

    undelivered = [d.seq for d in trip.drops if not d.delivered]
    if undelivered and not force:
        raise TransitionWarning(
            f"ยังส่งของไม่ครบ (เหลือจุด {undelivered}) — ยืนยันจบงานหรือไม่?"
        )

    trip.odometer_end = round(float(odometer_end), 1)
    if trip.odometer_start is not None:
        trip.distance_km = round(trip.odometer_end - trip.odometer_start, 2)
    trip.km_per_liter = compute_km_per_liter(trip)
    # หมายเหตุ: ไม่ปิดเที่ยวตรงนี้ — การ "จบเที่ยว" เป็นหน้าที่คนคุมงาน (complete_trip) เท่านั้น
    if undelivered:
        trip.override = True
    db.commit()
    db.refresh(trip)

    from app.services.finance import total_liters

    write_audit(
        db, who_label(actor), "จบงาน (เลขไมล์จบ)", trip.code,
        f"ไมล์จบ {trip.odometer_end:.1f} · ระยะทาง {trip.distance_km:.2f} กม. · "
        f"น้ำมันรวม {total_liters(trip):.2f} ลิตร · "
        + (f"{trip.km_per_liter} กม./ลิตร" if trip.km_per_liter is not None else "คิด กม./ลิตร ไม่ได้ (ไม่มีข้อมูลลิตร)"),
    )
    return trip


# ---------------------------------------------------------------------------
# GREEN → WHITE : Supervisor ปิดงาน (freeze) — ไม่อัตโนมัติ
# ---------------------------------------------------------------------------
def close_trip(
    db: Session, trip: Trip, actor: User, *, force: bool = False
) -> Trip:
    """Supervisor ล็อกการเงิน (ปิดบัญชีทริป) → freeze ถาวร

    หมายเหตุ flow ใหม่: การจบงาน (กลับ WHITE) เกิดอัตโนมัติเมื่อคนขับส่งครบทุกจุดแล้ว
    ขั้นตอนนี้เป็นการ "ล็อกการเงิน" ที่คนคุมงานกดหลังตรวจ/อนุมัติบิลเสร็จ

    การ์ด:
    - freeze แล้ว → ห้ามซ้ำ
    - ทริปต้องส่งของแล้ว (GREEN กำลังส่ง หรือจบงานแล้ว closed_at) — ยังไม่เริ่มส่ง = ล็อกไม่ได้
    - ยังส่งรูปไม่ครบทุกจุด → เตือนให้ยืนยัน (warn-don't-block, override ได้)
    """
    if trip.frozen:
        raise TransitionError(f"ทริป {trip.code} ถูกล็อกการเงินแล้ว")

    _assert_not_paused(trip)  # มีเหตุ SOS ค้าง → ปิดเหตุก่อนจึงล็อกการเงินได้

    # ต้องกด "จบเที่ยว" (Supervisor) ก่อนเท่านั้น จึงจะล็อกการเงินได้
    if trip.completed_at is None and trip.closed_at is None:
        raise TransitionError(
            f"ล็อกการเงินไม่ได้ — ต้องกด 'จบเที่ยว' ของทริป {trip.code} ก่อน "
            f"(ปัจจุบัน {trip.status.value} · เที่ยวหลักยัง Active)"
        )

    missing = [d.seq for d in trip.drops if not d.photo]
    if missing and not force:
        raise TransitionWarning(
            f"ยังส่งของไม่ครบ (ขาดจุด {missing}) — ยืนยันล็อกการเงินหรือไม่?"
        )

    # แช่ยอดน้ำมัน/ทางหลวงจากบิลที่ approved แล้ว ณ วินาทีล็อก (snapshot ถาวร)
    # import ในฟังก์ชันเพื่อเลี่ยง circular import (finance ไม่พึ่ง state_machine)
    from app.services.finance import compute_finance

    snapshot = compute_finance(trip)

    # หักยอดเบิกเงินล่วงหน้าที่อนุมัติแล้วของคนขับเข้าทริปนี้ (ข้อ 1.3)
    # ต้องหักก่อน commit freeze เพื่อให้ประทับ deducted_trip_id ใน transaction เดียวกัน
    from app.services.advance import deduct_advances_on_close

    advance_deducted = deduct_advances_on_close(db, trip)

    trip.status = TripStatus.WHITE
    trip.closed_at = trip.closed_at or _now()
    # คิด km/L ซ้ำตอนล็อก เผื่อมีบิลน้ำมันเข้ามาหลังกดจบงาน
    trip.km_per_liter = compute_km_per_liter(trip)
    trip.frozen = True
    trip.frozen_fuel = snapshot.fuel_total
    trip.frozen_toll = snapshot.toll_total
    if missing:
        trip.override = True
    db.commit()
    db.refresh(trip)

    write_audit(
        db, who_label(actor), "ล็อกการเงิน", trip.code,
        "freeze การเงิน (ปิดบัญชีทริป)"
        + (f" · override ขาดรูปจุด {missing}" if missing else " · รูปครบ")
        + (f" · หักเบิกล่วงหน้า {advance_deducted:.2f}" if advance_deducted else ""),
    )
    return trip
