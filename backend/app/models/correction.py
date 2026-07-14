"""Correction model — คำขอปลดล็อกแก้ไขตัวเลขการเงินของทริปที่ freeze แล้ว

ทางเดียวที่จะแก้ตัวเลข frozen ได้ ต้องผ่านคำขอนี้และให้ Super Admin อนุมัติ
เก็บค่าเก่า/ใหม่ ผู้ขอ ผู้อนุมัติ และเวลา ครบเพื่อ audit
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import CorrectionStatus


class Correction(Base):
    __tablename__ = "corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)  # เช่น C-01

    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"), nullable=False, index=True)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    requester_name: Mapped[str] = mapped_column(String(120), nullable=False)

    # field_key เช่น "fuel", "toll", "bonus", "penalty", "allowance:<dropId>"
    field_key: Mapped[str] = mapped_column(String(40), nullable=False)
    field_label: Mapped[str] = mapped_column(String(120), nullable=False)
    old_val: Mapped[float] = mapped_column(Float, nullable=False)
    new_val: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)  # บังคับกรอก

    status: Mapped[CorrectionStatus] = mapped_column(
        Enum(CorrectionStatus), nullable=False, default=CorrectionStatus.PENDING, index=True
    )
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Correction {self.code} {self.field_key} {self.status.value}>"
