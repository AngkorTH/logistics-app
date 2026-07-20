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


def upload_receipt(
    db: Session,
    drop: Drop,
    actor,
    kind: ReceiptKind,
    *,
    captured_at=None,  # เวลาอัปโหลดจริงตอนออฟไลน์ (Offline Auto-Sync) — None = ตอนนี้
    photo_b64: str | None = None,  # รูปถ่ายใบเสร็จจริง (บังคับ)
    liters: float | None = None,   # จำนวนลิตรที่เติม (บิลน้ำมัน) — ใช้คิด km/L ตอนจบงาน
) -> Receipt:
    """อัปบิลน้ำมัน/ทางหลวงรายจุดส่ง → สร้าง/อัปเดต Receipt เป็น Draft (approved=False)

    - 1 จุดมีบิลได้อย่างละ 1 ใบ (UniqueConstraint drop_id+kind) — อัปซ้ำถือเป็นการแก้ draft เดิม
    - **ไม่มี OCR**: ยอด = 0 · วันที่ = None เสมอ รอ Supervisor เปิดรูปแล้วพิมพ์เองตอนยืนยัน
    - รูปบิลบังคับ — เก็บ URL ไฟล์จริงลง DB
    """
    trip = drop.trip
    _guard_not_frozen(trip)

    from app.services.storage import save_photo_b64

    photo_path = save_photo_b64(photo_b64, "rcpt")
    if not photo_path:
        raise EvidenceError("ต้องแนบรูปบิลจริงมาด้วยเสมอ — ไม่มีรูป คนคุมงานตรวจยอดไม่ได้")

    receipt = (
        db.query(Receipt)
        .filter(Receipt.drop_id == drop.id, Receipt.kind == kind)
        .first()
    )
    if receipt is None:
        receipt = Receipt(drop_id=drop.id, kind=kind)
        db.add(receipt)
    # อัปโหลดใหม่/ซ้ำ = รีเซ็ตกลับเป็น draft ให้ Supervisor ตรวจใหม่เสมอ
    receipt.amount = 0.0   # ปิด OCR — ยอดจริงมาจากมือ Supervisor ตอน approve
    receipt.date = None    # ปิด OCR — วันที่บนบิลก็มาจากมือ Supervisor
    receipt.approved = False
    if liters is not None:
        if liters < 0:
            raise EvidenceError("จำนวนลิตรติดลบไม่ได้")
        receipt.liters = round(float(liters), 2)
    receipt.photo = photo_path
    if captured_at is not None:
        receipt.created_at = captured_at  # คงเวลาที่กดถ่าย/อัปจริง ไม่ใช่เวลา sync
    db.commit()
    db.refresh(receipt)

    write_audit(
        db, who_label(actor), "อัปโหลดบิล", trip.code,
        f"จุด {drop.seq} · {_KIND_LABEL[kind]} · รูป {photo_path} (รอคนคุมงานกรอกยอด/วันที่)",
    )
    # แจ้งเตือนเข้ากล่องจดหมายทีมคุมงาน: มีบิลใหม่รอเปิดรูปดูแล้วกรอกยอด
    push_notification(
        db, "BILL_UPLOADED", f"บิลใหม่รอกรอกยอด · {trip.code}",
        f"จุด {drop.seq} · {_KIND_LABEL[kind]} · เปิดรูปบิลแล้วกรอกยอดเงิน + วันที่", trip.id,
    )
    return receipt


def log_trip_receipt(
    db: Session,
    trip: Trip,
    actor,
    kind: ReceiptKind,
    *,
    photo_b64: str | None = None,   # รูปบิล/สลิป (Base64) — บังคับ
    liters: float | None = None,    # บังคับเฉพาะบิลน้ำมัน (ใช้คิด km/L)
    captured_at=None,
) -> Receipt:
    """อัปบิลระหว่างทาง (Mid-Trip) → Receipt ผูกกับทริปตรงๆ ไม่ผูกจุดส่ง

    ใช้ได้ตลอดเวลาที่คนขับยังวิ่งงานอยู่ (🟠 ไปขึ้นของ และ 🟢 กำลังไปส่ง) —
    แวะปั๊ม/ด่านเมื่อไหร่ก็ถ่ายส่งได้ทันที ไม่ต้องรอส่งของเสร็จ

    ต่างจาก upload_receipt (รายจุดส่ง): ไม่มี UniqueConstraint → อัปกี่ใบก็ได้ต่อทริป
    **ไม่มี OCR**: ยอดเงิน 0 · วันที่ None รอ Supervisor เปิดรูปแล้วคีย์เองตอนยืนยัน
    """
    _guard_not_frozen(trip)
    if kind is ReceiptKind.FUEL and (liters is None or liters <= 0):
        raise EvidenceError("บิลน้ำมันต้องระบุจำนวนลิตรที่เติม (มากกว่า 0)")

    from app.services.storage import save_photo_b64

    prefix = "fuel" if kind is ReceiptKind.FUEL else "toll"
    photo_path = save_photo_b64(photo_b64, prefix)
    if not photo_path:
        raise EvidenceError(f"ต้องแนบรูป{_KIND_LABEL[kind]}จริงมาด้วยเสมอ")

    receipt = Receipt(
        trip_id=trip.id,
        drop_id=None,
        kind=kind,
        amount=0.0,      # ปิด OCR — Supervisor กรอกยอดเองตอน approve
        liters=round(float(liters), 2) if liters else 0.0,
        date=None,       # ปิด OCR — Supervisor กรอกวันที่บนบิลเอง
        approved=False,
        photo=photo_path,
    )
    if captured_at is not None:
        receipt.created_at = captured_at
    db.add(receipt)
    db.commit()
    db.refresh(receipt)

    detail = f"{receipt.liters:.2f} ลิตร · " if kind is ReceiptKind.FUEL else ""
    write_audit(
        db, who_label(actor), f"อัปบิลระหว่างทาง ({_KIND_LABEL[kind]})", trip.code,
        f"{detail}แนบรูป {photo_path} (รอคนคุมงานกรอกยอด/วันที่)",
    )
    push_notification(
        db, "BILL_UPLOADED", f"บิลใหม่ระหว่างทาง · {trip.code}",
        f"{_KIND_LABEL[kind]} · {detail}เปิดรูปแล้วกรอกยอดเงิน + วันที่", trip.id,
    )
    return receipt


def log_fuel(db: Session, trip: Trip, actor, *, liters: float, photo_b64=None, captured_at=None):
    """ทางลัดเดิมสำหรับ 'แจ้งเติมน้ำมัน' — เรียก log_trip_receipt ด้วย kind=FUEL

    คงไว้เพื่อไม่ให้ endpoint /trips/{id}/fuel และคิว offline ที่ค้างอยู่พัง
    """
    return log_trip_receipt(
        db, trip, actor, ReceiptKind.FUEL,
        photo_b64=photo_b64, liters=liters, captured_at=captured_at,
    )


def approve_receipt(
    db: Session, receipt: Receipt, actor, *, amount: float, date: str
) -> Receipt:
    """Supervisor ยืนยันบิล — **กรอกยอดเงิน + วันที่เองจากรูป** (แทน OCR) → นับเข้ายอดจริง

    ทั้งสองค่าบังคับ: ไม่มี OCR มาเติมให้แล้ว ถ้าไม่กรอกก็ไม่มีข้อมูลบิล
    """
    _guard_not_frozen(receipt.owner_trip)
    if amount is None or amount < 0:
        raise EvidenceError("ต้องกรอกยอดเงินบนบิล (ไม่ติดลบ)")
    if not date or not date.strip():
        raise EvidenceError("ต้องกรอกวันที่บนบิลด้วยเสมอ")

    receipt.amount = round(float(amount), 2)
    receipt.date = date.strip()
    receipt.approved = True
    db.commit()
    db.refresh(receipt)

    write_audit(
        db, who_label(actor), "อนุมัติบิล (กรอกมือ)", receipt.owner_trip.code,
        f"{_where(receipt)} · {_KIND_LABEL[receipt.kind]} · ยอด {receipt.amount:.2f} · วันที่บิล {receipt.date}",
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
    """อัปรูปผ้าใบรายจุดส่ง → เก็บ URL ไฟล์รูปจริงลง DB

    soft — ไม่บังคับก่อนเปลี่ยนสถานะ (แค่เตือน) แต่ถ้า "จะอัป" ต้องมีรูปจริง
    ไม่มี marker "attached" อีกแล้ว
    """
    from app.services.storage import save_photo_b64

    _guard_not_frozen(drop.trip)
    photo_path = save_photo_b64(photo_b64, "tarp")
    if not photo_path:
        raise EvidenceError("ต้องแนบรูปผ้าใบจริงมาด้วย — ไม่มีรูป บันทึกไม่ได้")
    drop.tarp = photo_path
    db.commit()
    db.refresh(drop)
    write_audit(
        db, who_label(actor), "อัปโหลดรูปผ้าใบ", drop.trip.code, f"จุด {drop.seq} · {photo_path}",
    )
    return drop
