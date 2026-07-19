"""Evidence & OCR service — หลักฐาน 4 ปุ่มต่อ 1 จุดส่ง (skill.md ข้อ 3 และ 5)

4 ปุ่มหลักฐานต่อ 1 จุดส่ง (แยกรายจุด ไม่ให้เอกสารตีกัน):
    1) บิลน้ำมัน (FUEL)     → Receipt + OCR draft
    2) บิลทางหลวง (TOLL)    → Receipt + OCR draft
    3) รูปผ้าใบ (tarp)       → ตั้งธง drop.tarp
    4) รูปส่งของสำเร็จ       → อยู่ที่ state_machine.record_delivery (ผูก GPS ปลายทาง)

ปรัชญา OCR (สำคัญ — ห้ามพลาด): เมื่ออัปบิล ระบบดึงยอดมาตั้งเป็น **Draft**
(approved=False) ให้ Supervisor ตรวจก่อน ห้าม auto-commit เข้ายอดจริง
ยอด draft จะไม่ถูกนับรวมในการเงินจนกว่าจะ approve
"""
from sqlalchemy.orm import Session

from app.models import Drop, Receipt, Trip
from app.models.enums import ReceiptKind
from app.services.audit import who_label, write_audit
from app.services.notification import push_notification


class EvidenceError(Exception):
    """อัปโหลดหลักฐานไม่ได้ (เช่นทริป freeze แล้ว หรือ drop ไม่อยู่ในทริป)"""


_KIND_LABEL = {ReceiptKind.FUEL: "บิลน้ำมัน", ReceiptKind.TOLL: "บิลทางหลวง"}


def _where(receipt: Receipt) -> str:
    """ข้อความระบุที่มาของบิลใน audit log — รายจุดส่ง หรือเติมระหว่างทาง"""
    return f"จุด {receipt.drop.seq}" if receipt.drop is not None else "เติมระหว่างทาง"


def _guard_not_frozen(trip: Trip) -> None:
    """ทริปที่ปิดงาน (freeze) แล้ว ห้ามแนบหลักฐานเพิ่ม — ต้องขอ correction ก่อน"""
    if trip.frozen:
        raise EvidenceError(
            f"ทริป {trip.code} ถูกล็อกการเงินแล้ว (freeze) — แนบหลักฐานเพิ่มไม่ได้ ต้องขอปลดล็อกก่อน"
        )


def _fake_ocr(kind: ReceiptKind, raw_amount: float | None) -> float:
    """จำลอง AI OCR: คืนยอดที่ 'อ่านได้' จากบิล (stub)

    ของจริงจะส่งรูปเข้า OCR engine — ตอนนี้รับ raw_amount ที่ client ส่งมา
    (จำลองผลอ่าน) ถ้าไม่มีให้เป็น 0 เพื่อให้ Supervisor กรอกเอง
    """
    return round(float(raw_amount), 2) if raw_amount else 0.0


def upload_receipt(
    db: Session,
    drop: Drop,
    actor,
    kind: ReceiptKind,
    *,
    ocr_amount: float | None = None,
    ocr_date: str | None = None,
    captured_at=None,  # เวลาอัปโหลดจริงตอนออฟไลน์ (Offline Auto-Sync) — None = ตอนนี้
    photo_b64: str | None = None,  # รูปถ่ายใบเสร็จจริง (Phase 4)
    liters: float | None = None,   # จำนวนลิตรที่เติม (บิลน้ำมัน) — ใช้คิด km/L ตอนจบงาน
) -> Receipt:
    """อัปบิลน้ำมัน/ทางหลวงรายจุดส่ง → สร้าง/อัปเดต Receipt เป็น Draft (approved=False)

    - 1 จุดมีบิลได้อย่างละ 1 ใบ (UniqueConstraint drop_id+kind) — อัปซ้ำถือเป็นการแก้ draft เดิม
    - OCR ตั้งยอดเป็น draft เท่านั้น ยังไม่นับเข้ายอดจริงจนกว่า Supervisor จะ approve
    """
    trip = drop.trip
    _guard_not_frozen(trip)

    amount = _fake_ocr(kind, ocr_amount)
    receipt = (
        db.query(Receipt)
        .filter(Receipt.drop_id == drop.id, Receipt.kind == kind)
        .first()
    )
    if receipt is None:
        receipt = Receipt(drop_id=drop.id, kind=kind)
        db.add(receipt)
    # อัปโหลดใหม่/ซ้ำ = รีเซ็ตกลับเป็น draft ให้ Supervisor ตรวจใหม่เสมอ
    from app.services.storage import save_photo_b64

    receipt.amount = amount
    receipt.date = ocr_date
    receipt.approved = False
    if liters is not None:
        if liters < 0:
            raise EvidenceError("จำนวนลิตรติดลบไม่ได้")
        receipt.liters = round(float(liters), 2)
    photo_path = save_photo_b64(photo_b64, "rcpt")
    if photo_path:
        receipt.photo = photo_path
    if captured_at is not None:
        receipt.created_at = captured_at  # คงเวลาที่กดถ่าย/อัปจริง ไม่ใช่เวลา sync
    db.commit()
    db.refresh(receipt)

    write_audit(
        db, who_label(actor), "อัปโหลดบิล", trip.code,
        f"จุด {drop.seq} · {_KIND_LABEL[kind]} · OCR draft {amount:.2f} (รออนุมัติ)",
    )
    # แจ้งเตือนเข้ากล่องจดหมายทีมคุมงาน: มีบิลใหม่รอตรวจ/ยืนยันยอด
    push_notification(
        db, "BILL_UPLOADED", f"บิลใหม่รอตรวจ · {trip.code}",
        f"จุด {drop.seq} · {_KIND_LABEL[kind]} · ยอด OCR {amount:.2f} (รอยืนยัน)", trip.id,
    )
    return receipt


def log_fuel(
    db: Session,
    trip: Trip,
    actor,
    *,
    liters: float,
    photo_b64: str | None = None,   # รูปสลิปน้ำมัน (Base64)
    ocr_amount: float | None = None,
    ocr_date: str | None = None,
    captured_at=None,
) -> Receipt:
    """คนขับแจ้งเติมน้ำมันระหว่างทริป → Receipt (FUEL) ผูกกับทริปตรงๆ ไม่ผูกจุดส่ง

    ต่างจาก upload_receipt: เติมได้หลายครั้งต่อ 1 ทริป (ไม่มี UniqueConstraint)
    จำนวนลิตรทุกใบจะถูกรวมตอนจบงานเพื่อคิด km/L · ยอดเงินยังเป็น draft รอ Supervisor อนุมัติ
    """
    _guard_not_frozen(trip)
    if liters is None or liters <= 0:
        raise EvidenceError("ต้องระบุจำนวนลิตรที่เติม (มากกว่า 0)")

    from app.services.storage import save_photo_b64

    receipt = Receipt(
        trip_id=trip.id,
        drop_id=None,
        kind=ReceiptKind.FUEL,
        amount=_fake_ocr(ReceiptKind.FUEL, ocr_amount),
        liters=round(float(liters), 2),
        date=ocr_date,
        approved=False,
        photo=save_photo_b64(photo_b64, "fuel"),
    )
    if captured_at is not None:
        receipt.created_at = captured_at
    db.add(receipt)
    db.commit()
    db.refresh(receipt)

    write_audit(
        db, who_label(actor), "แจ้งเติมน้ำมัน", trip.code,
        f"{receipt.liters:.2f} ลิตร · OCR draft {receipt.amount:.2f} (รออนุมัติ)",
    )
    push_notification(
        db, "FUEL_LOGGED", f"แจ้งเติมน้ำมัน · {trip.code}",
        f"{receipt.liters:.2f} ลิตร · ยอด OCR {receipt.amount:.2f} (รอยืนยัน)", trip.id,
    )
    return receipt


def approve_receipt(db: Session, receipt: Receipt, actor, *, amount: float | None = None) -> Receipt:
    """Supervisor ยืนยันยอดบิล (แก้ยอดได้ก่อน approve) → approved=True นับเข้ายอดจริง"""
    _guard_not_frozen(receipt.owner_trip)
    if amount is not None:
        receipt.amount = round(float(amount), 2)
    receipt.approved = True
    db.commit()
    db.refresh(receipt)

    write_audit(
        db, who_label(actor), "อนุมัติบิล", receipt.owner_trip.code,
        f"{_where(receipt)} · {_KIND_LABEL[receipt.kind]} · ยืนยัน {receipt.amount:.2f}",
    )
    return receipt


def edit_receipt_amount(db: Session, receipt: Receipt, actor, new_amount: float, reason: str) -> Receipt:
    """แก้ยอดเงินใบเสร็จ OCR แบบ Manual (Supervisor+) — บังคับเหตุผลเสมอ (task 2)

    ต่างจาก approve: ใช้แก้ยอดได้ทั้งบิล draft และบิลที่อนุมัติแล้ว (ยังไม่ freeze)
    ทุกครั้งบันทึกลง Audit Trail: ใครแก้ · บิลของทริป/จุดไหน · ยอดเดิม→ใหม่ · เหตุผล
    """
    _guard_not_frozen(receipt.owner_trip)
    if not reason or not reason.strip():
        raise EvidenceError("ต้องระบุเหตุผลการแก้ไขยอดเงินเสมอ")
    if new_amount < 0:
        raise EvidenceError("ยอดเงินติดลบไม่ได้")

    old = receipt.amount
    receipt.amount = round(float(new_amount), 2)
    db.commit()
    db.refresh(receipt)

    write_audit(
        db, who_label(actor), "แก้ยอดเงินใบเสร็จ (OCR)", receipt.owner_trip.code,
        f"{_where(receipt)} · {_KIND_LABEL[receipt.kind]} · {old:.2f} → {receipt.amount:.2f} · เหตุผล: {reason.strip()}",
    )
    return receipt


def upload_tarp(db: Session, drop: Drop, actor, *, photo_b64: str | None = None) -> Drop:
    """อัปรูปผ้าใบรายจุดส่ง → เก็บรูปจริง (Phase 4) · soft — ไม่บังคับก่อนเปลี่ยนสถานะ"""
    from app.services.storage import save_photo_b64

    _guard_not_frozen(drop.trip)
    drop.tarp = save_photo_b64(photo_b64, "tarp") or "attached"
    db.commit()
    db.refresh(drop)
    write_audit(
        db, who_label(actor), "อัปโหลดรูปผ้าใบ", drop.trip.code, f"จุด {drop.seq}",
    )
    return drop
