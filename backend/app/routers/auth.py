"""Router: Authentication (login / me / logout)"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.security import create_access_token, new_session_token, verify_password
from app.services.audit import who_label, write_audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """เข้าสู่ระบบด้วยเบอร์โทร/รหัสพนักงาน + รหัสผ่าน

    จุดสำคัญ (Single-Session Lock): ทุกครั้งที่ login สำเร็จจะสร้าง session token ใหม่
    แล้วเขียนทับ user.session_id — token เก่าของเครื่องอื่นจะใช้ไม่ได้ทันที (ถูกดีดออก)
    """
    ident = body.identifier.strip()
    user = (
        db.query(User)
        .filter(or_(User.phone == ident, User.emp_id == ident))
        .first()
    )
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "เบอร์โทร/รหัสพนักงาน หรือรหัสผ่านไม่ถูกต้อง")
    if not user.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "บัญชีนี้ถูกระงับการใช้งาน")

    had_session = bool(user.session_id)
    sid = new_session_token()
    user.session_id = sid  # ทับ session เก่า = ดีดเครื่องเดิมออก
    db.commit()

    token = create_access_token(user.id, sid)
    write_audit(
        db, who_label(user), "เข้าสู่ระบบ", user.emp_id,
        f"Single session{' — ดีด session เก่าออก' if had_session else ''} · {user.role.value}",
    )
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    """คืนข้อมูลผู้ใช้ปัจจุบัน — ใช้ตรวจว่า token/session ยังใช้ได้อยู่ไหม"""
    return UserOut.model_validate(user)


@router.post("/logout")
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """ออกจากระบบ — ล้าง session_id ทำให้ token ปัจจุบันใช้ไม่ได้อีก"""
    user.session_id = None
    db.commit()
    write_audit(db, who_label(user), "ออกจากระบบ", user.emp_id, "ล้าง session")
    return {"detail": "ออกจากระบบแล้ว"}
