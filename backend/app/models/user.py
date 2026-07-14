"""User model — พนักงานทุกระดับ (Driver / Supervisor / Admin / Super Admin)"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import Role


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # emp_id = รหัสพนักงานที่มนุษย์อ่าน (เช่น D01, SV01) ใช้ login ได้เหมือนเบอร์โทร
    emp_id: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False, default=Role.DRIVER)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # คะแนนดาวคนขับ 0-5 — Admin/Super Admin ตั้งได้ Frontend แสดงเป็นรูปดาวเท่านั้น
    rating: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # เก็บ hash เท่านั้น ห้ามเก็บรหัสผ่านดิบ (จะใช้เต็มรูปแบบตอนทำ Auth ใน Step 1 ส่วน 2)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Single Session: token ล่าสุด — login ที่อื่นจะทับค่านี้ = ดีดเครื่องเก่าออก
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    vehicles = relationship("Vehicle", back_populates="driver")
    trips = relationship("Trip", back_populates="driver")

    def __repr__(self) -> str:
        return f"<User {self.emp_id} {self.name} ({self.role.value})>"
