"""Audit Middleware — ดักจับทุก request ที่เปลี่ยนแปลงข้อมูล (POST/PUT/PATCH/DELETE)
แล้วบันทึกลงตาราง audit_logs เป็น baseline ว่าใครเรียก endpoint ไหน เวลาไหน

หมายเหตุ: endpoint เชิงธุรกิจ (จ่ายงาน/หักเงิน ฯลฯ) จะเขียน audit ที่ละเอียดกว่าเองอีกชั้น
middleware นี้จึงข้าม /auth (endpoint บันทึกเองแล้ว) และบันทึกเฉพาะ request ที่สำเร็จ
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.database import SessionLocal
from app.models import User
from app.security import decode_access_token
from app.services.audit import who_label, write_audit

_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
_SKIP_PREFIXES = ("/auth", "/docs", "/openapi", "/redoc")


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        path = request.url.path
        if (
            request.method in _MUTATING
            and response.status_code < 400
            and not path.startswith(_SKIP_PREFIXES)
        ):
            self._record(request, path)
        return response

    def _record(self, request: Request, path: str) -> None:
        """ระบุตัวผู้กระทำจาก Bearer token (ถ้ามี) แล้วเขียน log — แยก DB session ของตัวเอง"""
        db = SessionLocal()
        try:
            user = None
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                payload = decode_access_token(auth.split(" ", 1)[1])
                if payload:
                    user = db.get(User, int(payload.get("sub", 0)))
            write_audit(db, who_label(user), f"{request.method} {path}", "API", "auto-captured")
        except Exception:
            db.rollback()  # ห้ามให้การเขียน log ล้ม แล้วกระทบ response หลัก
        finally:
            db.close()
