"""GpsLog model — บันทึกพิกัด GPS Geofencing ตอน Driver กดเปลี่ยนสถานะ

ตาม skill.md ข้อ 5: บันทึกพิกัดอัตโนมัติเมื่อกด "ขนของขึ้นเสร็จแล้ว" (ต้นทาง)
และเมื่อส่งของสำเร็จในแต่ละจุด (ปลายทาง) — logic การเขียนจะทำใน Step 2
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import GpsEvent


class GpsLog(Base):
    __tablename__ = "gps_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"), nullable=False, index=True)
    # drop_id เป็น null สำหรับ event ต้นทาง (LOADED); มีค่าเมื่อเป็นการส่งรายจุด (DELIVERED)
    drop_id: Mapped[int | None] = mapped_column(ForeignKey("drops.id"), nullable=True)

    event: Mapped[GpsEvent] = mapped_column(Enum(GpsEvent), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self) -> str:
        return f"<GpsLog trip={self.trip_id} {self.event.value} {self.lat},{self.lng}>"
