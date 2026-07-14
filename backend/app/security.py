"""ฟังก์ชันความปลอดภัยระดับต่ำ: hash รหัสผ่าน + สร้าง/ถอด JWT

JWT ฝัง 2 อย่างที่สำคัญ:
- sub : id ของผู้ใช้
- sid : session token ล่าสุด (ใช้ทำ Single-Session Lock — เทียบกับ user.session_id ใน DB)
"""
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(raw: str) -> str:
    return pwd_context.hash(raw)


def verify_password(raw: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    return pwd_context.verify(raw, hashed)


def new_session_token() -> str:
    """สร้าง token สุ่มสำหรับ 1 session (1 อุปกรณ์)"""
    return secrets.token_hex(16)


def create_access_token(user_id: int, session_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "sid": session_id, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """ถอด JWT — คืน payload ถ้าถูกต้อง, None ถ้าไม่ถูกต้อง/หมดอายุ"""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
