"""Notification model — กล่องจดหมายแจ้งเตือนฝั่งบริหาร (Supervisor/Admin)

ใช้เป็น inbox กลางของทีมคุมงาน — เช่น "คนขับส่งภาพบิลเข้ามา", "ทริปจบงานอัตโนมัติ"
Driver ไม่เกี่ยวข้อง (ไม่มีสิทธิ์อ่าน) — read เป็นธงรวมของกล่องบริหาร
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)   # BILL_UPLOADED / TRIP_DONE ...
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    trip_id: Mapped[int | None] = mapped_column(ForeignKey("trips.id"), nullable=True, index=True)
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    def __repr__(self) -> str:
        return f"<Notification {self.kind} read={self.read}>"
