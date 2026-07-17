"""FastAPI application entrypoint"""
from fastapi import Depends
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.deps import require_admin
from app.middleware import AuditMiddleware
from app.models import User
from app.routers import (
    advances,
    audit,
    auth,
    correction,
    dispatch,
    evidence,
    finance,
    incidents,
    inspections,
    maintenance,
    notifications,
    penalties,
    trips,
    users,
    vehicles,
)

app = FastAPI(title="Logistics ERP API", version="0.1.0")

# CORS สำหรับ frontend (Vite dev server) — ปรับ origin จริงตอน deploy
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuditMiddleware)

# Phase 4: เสิร์ฟรูปหลักฐานจริงจากโฟลเดอร์ uploads/ (สร้างอัตโนมัติ)
from app.services.storage import UPLOAD_DIR

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

app.include_router(auth.router)
app.include_router(trips.router)
app.include_router(evidence.router)
app.include_router(finance.router)
app.include_router(correction.router)
app.include_router(dispatch.router)
app.include_router(penalties.router)
app.include_router(users.router)
app.include_router(vehicles.router)
app.include_router(audit.router)
app.include_router(notifications.router)
app.include_router(inspections.router)
app.include_router(advances.router)
app.include_router(incidents.router)
app.include_router(maintenance.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


@app.get("/admin/ping", tags=["health"])
def admin_ping(user: User = Depends(require_admin)):
    """endpoint ตัวอย่างสำหรับทดสอบ require_role — เข้าได้เฉพาะ Admin/Super Admin"""
    return {"detail": f"สวัสดี {user.name} — คุณมีสิทธิ์ระดับ {user.role.value}"}
