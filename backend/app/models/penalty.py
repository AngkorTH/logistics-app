"""Penalty model — รายการหักเงินแบบหลายบรรทัด ผูก User(คนขับ) + Trip

ต่างจากฟิลด์ `penalty` เดิมบน Trip (ยอดรวมก้อนเดียว) — โมเดลนี้เก็บได้หลายรายการ
แต่ละรายการต้องระบุ "เหตุผลเสมอ" (skill.md ข้อ 3) และหักจากเบี้ยเลี้ยงเท่านั้น
Supervisor/Admin เพิ่มได้ · Driver เข้าถึงไม่ได้เด็ดขาด
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Penalty(Base):
    __tablename__ = "penalties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"), nullable=False, index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)  # ยอดหัก (บาท)
    reason: Mapped[str] = mapped_column(Text, nullable=False)                # บังคับกรอกเสมอ

    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    creator_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    trip = relationship("Trip")
    driver = relationship("User", foreign_keys=[driver_id])

    def __repr__(self) -> str:
        return f"<Penalty trip={self.trip_id} driver={self.driver_id} {self.amount}>"
