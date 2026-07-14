"""Inspection model — ตรวจสภาพรถก่อนวิ่ง (Pre-trip Inspection)

Flow: หลังได้รับงาน (ORANGE) คนขับต้องส่ง checklist ตรวจสภาพรถก่อน
จึงจะกด "ขนของขึ้นเสร็จ" (→GREEN) ได้
- ติ๊กผ่านทุกข้อ → PASSED เริ่มงานได้ทันที
- มีจุดชำรุด → บังคับถ่ายรูป + PENDING_REVIEW รอคุมงาน/แอดมินประเมิน (APPROVED/REJECTED)
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text  # Boolean ยังใช้กับ passed
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import InspectionStatus


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"), nullable=False, index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    # ผลติ๊ก checklist เก็บเป็น JSON string เช่น {"tires": true, "lights": true, "tarp": false}
    items: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # ผ่านครบทุกข้อ
    defect_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Phase 4: URL รูปจุดชำรุด (/uploads/..) — None = ไม่มีรูป
    defect_photo: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[InspectionStatus] = mapped_column(
        Enum(InspectionStatus), nullable=False, default=InspectionStatus.PASSED, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewer_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    trip = relationship("Trip")
    driver = relationship("User", foreign_keys=[driver_id])

    def __repr__(self) -> str:
        return f"<Inspection trip={self.trip_id} {self.status.value}>"
