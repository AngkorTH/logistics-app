"""MaintenanceReport model — คนขับแจ้งเหตุ/รถมีปัญหา ตอนรองาน (สถานะขาว)

ต่างจาก Incident (SOS ระหว่างทริปที่กำลังวิ่ง): อันนี้ผูกกับ "รถ" ไม่ใช่ทริป
Flow: คนขับพิมพ์รายละเอียด + แนบรูปหลักฐาน → ระบบตั้งรถเป็น MAINTENANCE
(ล็อกไม่ให้คุมงานจ่ายงาน) + เด้งแจ้งเตือนคุมงาน/แอดมิน · คุมงานปิดเหตุ (RESOLVED)
รถจึงกลับเป็น AVAILABLE
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import IncidentStatus


class MaintenanceReport(Base):
    __tablename__ = "maintenance_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)  # เช่น MR-01

    driver_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # รถที่แจ้ง — nullable เผื่อคนขับยังไม่ถูกผูกรถ (ยังบันทึกประวัติแจ้งเหตุได้)
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"), nullable=True, index=True)
    plate: Mapped[str] = mapped_column(String(50), nullable=False, default="")  # snapshot ทะเบียนตอนแจ้ง

    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    photo: Mapped[str | None] = mapped_column(String(255), nullable=True)  # URL รูปหลักฐาน (/uploads/..)

    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus), nullable=False, default=IncidentStatus.OPEN, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolver_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    resolver_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    driver = relationship("User", foreign_keys=[driver_id])
    vehicle = relationship("Vehicle", foreign_keys=[vehicle_id])

    def __repr__(self) -> str:
        return f"<MaintenanceReport {self.code} {self.plate} {self.status.value}>"
