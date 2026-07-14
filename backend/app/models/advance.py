"""Advance model — คำขอเบิกเงินล่วงหน้าของคนขับ

Flow: คนขับระบุยอด + เหตุผล → คุมงาน/แอดมิน/ซุปเปอร์แอดมินอนุมัติ
ยอดที่ APPROVED จะถูก "หักลบ" กับเบี้ยเลี้ยงสุทธิอัตโนมัติตอนปิดทริป (close_trip)
โดยประทับ deducted_trip_id/deducted_at กันหักซ้ำ
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import AdvanceStatus


class Advance(Base):
    __tablename__ = "advances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)  # เช่น A-01

    driver_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # ทริปที่ขอระหว่างวิ่ง (อาจว่างถ้าขอตอนไม่มีทริป — ไปหักกับทริปถัดไปที่ปิด)
    trip_id: Mapped[int | None] = mapped_column(ForeignKey("trips.id"), nullable=True, index=True)

    amount: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)  # บังคับกรอกเสมอ

    status: Mapped[AdvanceStatus] = mapped_column(
        Enum(AdvanceStatus), nullable=False, default=AdvanceStatus.PENDING, index=True
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decider_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ประทับตอนถูกหักจริงตอนปิดทริป — กันหักซ้ำ
    deducted_trip_id: Mapped[int | None] = mapped_column(ForeignKey("trips.id"), nullable=True)
    deducted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    driver = relationship("User", foreign_keys=[driver_id])

    def __repr__(self) -> str:
        return f"<Advance {self.code} {self.amount} {self.status.value}>"
