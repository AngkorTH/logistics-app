"""Trip / Drop / Receipt models — หัวใจของ Business Logic

- Trip  = ทริปหลัก 1 ใบ (ผูกคนขับ + ทะเบียน + สถานะ 3 สี + ยอดเงินที่ freeze ตอนปิดงาน)
- Drop  = จุดส่งย่อย 1-5 จุดต่อทริป (Multi-Drop)
- Receipt = บิลน้ำมัน/ทางหลวง แยกรายจุดส่ง (OCR draft — นับเข้ายอดเมื่อ approved เท่านั้น)
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ReceiptKind, TripDifficulty, TripStatus


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)  # เช่น T-001

    driver_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    plate: Mapped[str | None] = mapped_column(String(50), nullable=True)  # ผูกตอนจ่ายงาน
    distance_km: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    status: Mapped[TripStatus] = mapped_column(
        Enum(TripStatus), nullable=False, default=TripStatus.WHITE, index=True
    )
    # ความยากของทริป — Supervisor ตั้งตอนจ่ายงาน ใช้จัดลำดับคิวคนขับ (Smart Dispatch)
    difficulty: Mapped[TripDifficulty] = mapped_column(
        Enum(TripDifficulty), nullable=False, default=TripDifficulty.MEDIUM
    )
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_loading_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Escalation ผ้าใบ
    tarpaulin_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tarp_escalated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # การเงินระดับทริป
    bonus: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    penalty: Mapped[float] = mapped_column(Float, nullable=False, default=0)  # หักจากเบี้ยเลี้ยงทริปเท่านั้น
    penalty_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # ยอดน้ำมัน/ทางหลวงที่ freeze ตอนปิดงาน (ก่อนปิดงานให้คำนวณจาก receipt ที่ approved)
    frozen_fuel: Mapped[float | None] = mapped_column(Float, nullable=True)
    frozen_toll: Mapped[float | None] = mapped_column(Float, nullable=True)

    # เลขไมล์ + อัตราสิ้นเปลือง (Phase 5)
    # odometer_start ตั้งตอนจ่ายงาน · odometer_end ส่งตอนจบงาน (End Trip)
    odometer_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    odometer_end: Mapped[float | None] = mapped_column(Float, nullable=True)
    # รูปหน้าปัดไมล์ตอนเริ่มงาน — บังคับถ่ายคู่กับเลขไมล์ (ไว้ให้แอดมินเทียบกับเลขที่พิมพ์)
    odometer_start_photo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # รูปหน้าปัดไมล์ตอนจบงาน (End Trip) — บังคับถ่ายคู่กับเลขไมล์จบเสมอ
    odometer_end_photo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # km/L = (ไมล์จบ − ไมล์เริ่ม) / ลิตรรวมที่เติมในทริป · ลิตรรวม 0 → None (กันหารศูนย์)
    km_per_liter: Mapped[float | None] = mapped_column(Float, nullable=True)

    # SOS/Incident — ทริปถูกล็อกสถานะชั่วคราวเมื่อมีเหตุฉุกเฉิน OPEN อยู่
    paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Dynamic Multi-Drop: เที่ยวหลักยัง "Active" อยู่แม้คนขับส่งงานย่อยเสร็จหมดแล้ว
    # จบสมบูรณ์เมื่อ Supervisor กด "จบเที่ยว" เท่านั้น (คนละขั้นกับการล็อกการเงิน)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Freeze on Close
    frozen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # ปิดงานข้ามขั้นตอน
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    driver = relationship("User", back_populates="trips")
    drops = relationship(
        "Drop", back_populates="trip", cascade="all, delete-orphan", order_by="Drop.seq"
    )
    # บิลที่ผูกกับ "ทริป" ตรงๆ ไม่ผูกจุดส่ง — ใช้กับการแจ้งเติมน้ำมันระหว่างทาง
    # (บิลรายจุดส่งยังอยู่ที่ Drop.receipts เหมือนเดิม และมี trip_id = NULL)
    trip_receipts = relationship(
        "Receipt", back_populates="trip", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Trip {self.code} {self.status.value}>"


class Drop(Base):
    __tablename__ = "drops"
    __table_args__ = (
        UniqueConstraint("trip_id", "seq", name="uq_drop_trip_seq"),
        # DB Security: ต้นทาง/ปลายทางห้ามว่างระดับฐานข้อมูล (NOT NULL + ความยาว > 0)
        CheckConstraint("length(trim(origin)) > 0", name="ck_drop_origin_not_blank"),
        CheckConstraint("length(trim(destination)) > 0", name="ck_drop_destination_not_blank"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)  # ลำดับจุด 1-5

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Dynamic Multi-Drop: ทุกงานย่อยต้องระบุต้นทาง→ปลายทางเสมอ
    # บังคับ 3 ชั้น: Pydantic (min_length=1) → NOT NULL → CheckConstraint ความยาว > 0
    # ไม่มี default แล้ว — สร้าง Drop โดยไม่ใส่ต้นทาง/ปลายทาง = IntegrityError ทันที
    origin: Mapped[str] = mapped_column(String(255), nullable=False)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    # รายได้ของขานี้ (คนคุมงานกรอกตอนจ่ายงาน) — ฐานคิดเบี้ยเลี้ยง
    revenue: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    # ความยากรายขา — ตัวคูณเปอร์เซ็นต์เบี้ยเลี้ยง (ง่าย 5% · ปานกลาง 7% · ยาก 10%)
    difficulty: Mapped[TripDifficulty] = mapped_column(
        Enum(TripDifficulty), nullable=False, default=TripDifficulty.MEDIUM
    )
    # เบี้ยเลี้ยงขานี้ = revenue × เปอร์เซ็นต์ความยาก (ระบบคิดให้ ไม่ให้กรอกมือ)
    allowance: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    # รูป "ของที่ขนขึ้นรถแล้ว" — คนขับถ่ายตอนกดยืนยันขนของเสร็จ (ORANGE → GREEN)
    # nullable เพราะขาเก่าก่อนมีด่านนี้ไม่มีรูป
    loaded_photo: Mapped[str | None] = mapped_column(String(255), nullable=True)

    delivered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Phase 4: เก็บ URL รูปจริง (/uploads/..) — None = ยังไม่มีรูป · "attached" = ข้อมูลเก่าก่อนมีระบบไฟล์
    photo: Mapped[str | None] = mapped_column(String(255), nullable=True)  # รูปส่งสำเร็จ
    tarp: Mapped[str | None] = mapped_column(String(255), nullable=True)   # รูปผ้าใบ
    gps: Mapped[str | None] = mapped_column(String(60), nullable=True)           # พิกัดปลายทาง
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    trip = relationship("Trip", back_populates="drops")
    receipts = relationship("Receipt", back_populates="drop", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Drop {self.seq} {self.name}>"


class Receipt(Base):
    __tablename__ = "receipts"
    # 1 จุดส่งมีบิลได้อย่างละ 1 ใบ (น้ำมัน 1 + ทางหลวง 1) — กันเอกสารตีกัน
    __table_args__ = (UniqueConstraint("drop_id", "kind", name="uq_receipt_drop_kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # บิลรายจุดส่ง → drop_id · บิลแจ้งเติมน้ำมันระหว่างทาง → trip_id (drop_id = NULL)
    drop_id: Mapped[int | None] = mapped_column(ForeignKey("drops.id"), nullable=True, index=True)
    trip_id: Mapped[int | None] = mapped_column(ForeignKey("trips.id"), nullable=True, index=True)
    kind: Mapped[ReceiptKind] = mapped_column(Enum(ReceiptKind), nullable=False)

    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)  # ยอดจาก OCR/แก้เอง
    liters: Mapped[float] = mapped_column(Float, nullable=False, default=0)  # จำนวนลิตรที่เติม (บิลน้ำมัน)
    date: Mapped[str | None] = mapped_column(String(40), nullable=True)      # วันที่บนบิล (จาก OCR)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # False = Draft
    photo: Mapped[str | None] = mapped_column(String(255), nullable=True)  # รูปถ่ายใบเสร็จจริง (Phase 4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    drop = relationship("Drop", back_populates="receipts")
    trip = relationship("Trip", back_populates="trip_receipts")

    @property
    def owner_trip(self) -> "Trip":
        """ทริปเจ้าของบิล — ผ่านจุดส่ง (บิลรายจุด) หรือผูกตรง (บิลเติมน้ำมันระหว่างทาง)"""
        return self.drop.trip if self.drop is not None else self.trip

    def __repr__(self) -> str:
        return f"<Receipt {self.kind.value} {self.amount} approved={self.approved}>"
