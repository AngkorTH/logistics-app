"""Incident model — แจ้งเหตุฉุกเฉินระหว่างทริป (SOS / Incident Report)

Flow: คนขับกด SOS + ถ่ายรูป + ส่งพิกัด → ทริปถูก pause (Trip.paused = True)
และแจ้งเตือนสีแดงเด้งไปหน้าคุมงาน/แอดมินทันที · คุมงานกดปิดเหตุ (RESOLVED)
ทริปจึงกลับมาวิ่งต่อได้
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import IncidentKind, IncidentStatus


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)  # เช่น S-01

    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"), nullable=False, index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    kind: Mapped[IncidentKind] = mapped_column(
        Enum(IncidentKind), nullable=False, default=IncidentKind.BREAKDOWN
    )
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    gps: Mapped[str | None] = mapped_column(String(60), nullable=True)   # พิกัดจุดเกิดเหตุ
    # Phase 4: URL รูปหน้างาน (/uploads/..) — None = ไม่มีรูป
    photo: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus), nullable=False, default=IncidentStatus.OPEN, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolver_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    trip = relationship("Trip")
    driver = relationship("User", foreign_keys=[driver_id])

    def __repr__(self) -> str:
        return f"<Incident {self.code} {self.kind.value} {self.status.value}>"
