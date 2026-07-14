"""FastAPI dependencies สำหรับ Auth & Authorization

- get_current_user : ตรวจ JWT + บังคับ Single-Session (เทียบ sid ใน token กับ user.session_id)
- require_role     : factory สร้าง dependency ตรวจสิทธิ์ตาม Role
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Drop, Role, Trip, User
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "ต้องแนบ token เพื่อเข้าใช้งาน")

    payload = decode_access_token(creds.credentials)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token ไม่ถูกต้องหรือหมดอายุ")

    user = db.get(User, int(payload.get("sub", 0)))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "ไม่พบผู้ใช้")
    if not user.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "บัญชีนี้ถูกระงับการใช้งาน")

    # ---- Single-Session Lock ----
    # ถ้า sid ใน token ไม่ตรงกับ session_id ล่าสุดใน DB แปลว่ามีคน login เครื่องใหม่ทับไปแล้ว
    # → token ของแท็บนี้เป็นของ session เก่า ให้ดีดออกทันที
    if payload.get("sid") != user.session_id:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "บัญชีนี้ถูกเข้าใช้งานจากอุปกรณ์อื่น — session นี้ถูกดีดออก (1 บัญชี = 1 Session)",
        )
    return user


def require_role(*allowed: Role):
    """สร้าง dependency ที่ยอมให้เฉพาะ Role ที่กำหนดเท่านั้นเข้าถึง endpoint"""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"สิทธิ์ไม่พอ — ต้องเป็น {', '.join(r.value for r in allowed)}",
            )
        return user

    return checker


# ทางลัดที่ใช้บ่อย
require_supervisor = require_role(Role.SUPERVISOR, Role.ADMIN, Role.SUPER_ADMIN)
require_admin = require_role(Role.ADMIN, Role.SUPER_ADMIN)
require_super_admin = require_role(Role.SUPER_ADMIN)


# ---------------------------------------------------------------------------
# Ownership guard — กันไม่ให้ Driver ดึง/แก้ข้อมูลของทริปที่ไม่ใช่ของตนเอง
# (claude.md ข้อ 3: "Backend ต้องตรวจ Token เสมอ เพื่อป้องกัน Driver ดึงข้อมูลข้ามคน")
# ---------------------------------------------------------------------------
def _assert_trip_access(user: User, trip: Trip) -> None:
    """Supervisor/Admin เห็นได้ทุกทริป · Driver เห็นได้เฉพาะทริปของตัวเองเท่านั้น"""
    if user.role is Role.DRIVER and trip.driver_id != user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "คุณไม่มีสิทธิ์เข้าถึงทริปนี้ — ดูได้เฉพาะทริปของตนเองเท่านั้น",
        )


def get_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Trip:
    """โหลดทริปตาม id + เช็ก ownership ให้อัตโนมัติ (ใช้เป็น dependency ใน path ที่มี {trip_id})"""
    trip = db.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบทริป")
    _assert_trip_access(user, trip)
    return trip


def get_drop(
    drop_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Drop:
    """โหลดจุดส่งตาม id + เช็ก ownership ผ่านทริปแม่"""
    drop = db.get(Drop, drop_id)
    if not drop:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบจุดส่ง")
    _assert_trip_access(user, drop.trip)
    return drop
