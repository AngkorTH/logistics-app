"""Pydantic schemas สำหรับ Auth"""
from pydantic import BaseModel, ConfigDict

from app.models.enums import Role


class LoginRequest(BaseModel):
    # ล็อกอินด้วยเบอร์โทร หรือ รหัสพนักงาน (emp_id) + รหัสผ่าน
    identifier: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    emp_id: str
    name: str
    phone: str
    role: Role
    active: bool
    notif: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
