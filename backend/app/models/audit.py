"""AuditLog model — บันทึกทุก action สำคัญ: ใคร / ทำอะไร / ข้อมูลไหน / เวลาใด

ตาม claude.md: จ่ายงาน, เปลี่ยนสถานะ, คีย์เงิน, หักเงิน ฯลฯ ต้องถูกบันทึกลง log ทั้งหมด
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    who: Mapped[str] = mapped_column(String(160), nullable=False)     # เช่น "ธนพล คุมงาน (SV01)"
    action: Mapped[str] = mapped_column(String(160), nullable=False)  # เช่น "จ่ายงาน"
    target: Mapped[str] = mapped_column(String(80), nullable=False, default="—")  # เช่น "T-001"
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} {self.target}>"
