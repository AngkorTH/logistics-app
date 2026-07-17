"""Vehicle model — ทะเบียนรถ (Vehicle Inventory) ผูกกับคนขับได้ 1 คน"""
from sqlalchemy import Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import VehicleStatus


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plate: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    # อัตราสิ้นเปลืองมาตรฐาน (กม./ลิตร) — ใช้ตรวจจับการใช้น้ำมันผิดปกติ
    std_km_l: Mapped[float] = mapped_column(Float, nullable=False, default=3.5)
    # สถานะรถ — MAINTENANCE = คนขับแจ้งเหตุรถมีปัญหา → ล็อกไม่ให้จ่ายงาน
    status: Mapped[VehicleStatus] = mapped_column(
        Enum(VehicleStatus), nullable=False, default=VehicleStatus.AVAILABLE, index=True
    )

    driver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    driver = relationship("User", back_populates="vehicles")

    def __repr__(self) -> str:
        return f"<Vehicle {self.plate} ({self.model})>"
