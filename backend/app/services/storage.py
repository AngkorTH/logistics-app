"""Storage Layer — เก็บไฟล์รูปหลักฐานจริง (Phase 4)

รับรูปเป็น Base64 (data URL หรือ raw) ใน JSON body — เลือกทางนี้เพราะ
"เข้ากันได้ 100% กับ Offline Auto-Sync" (Phase 3B): คิว IndexedDB เก็บ/ส่ง JSON
เดิมได้เลย ไม่ต้องแยกจัดการ multipart ตอน flush

ไฟล์ถูกเขียนลง backend/uploads/ แล้วเสิร์ฟผ่าน StaticFiles ที่ /uploads/<ชื่อไฟล์>
ค่าที่เก็บใน DB คือ URL path เช่น "/uploads/dlv-a1b2c3.jpg"
"""
import base64
import re
import uuid
from pathlib import Path

# backend/uploads (ข้างโฟลเดอร์ app) — สร้างอัตโนมัติเมื่อบันทึกไฟล์แรก
UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
MAX_BYTES = 8 * 1024 * 1024  # 8MB — กันรูปยักษ์ทำ DB/คิว offline บวม

_ALLOWED_EXT = {"jpg", "jpeg", "png", "webp", "gif"}
_DATA_URL = re.compile(r"^data:image/(\w+);base64,(.+)$", re.S)


class StorageError(Exception):
    """ไฟล์รูปใช้ไม่ได้ (base64 พัง / ใหญ่เกิน / ชนิดไม่รองรับ)"""


def save_photo_b64(b64: str | None, prefix: str) -> str | None:
    """แปลง Base64 → ไฟล์ใน uploads/ · คืน URL path หรือ None ถ้าไม่ส่งรูปมา"""
    if not b64 or not b64.strip():
        return None

    m = _DATA_URL.match(b64.strip())
    ext, payload = (m.group(1).lower(), m.group(2)) if m else ("jpg", b64.strip())
    if ext == "jpeg":
        ext = "jpg"
    if ext not in _ALLOWED_EXT:
        raise StorageError(f"ชนิดรูป .{ext} ไม่รองรับ — ใช้ jpg/png/webp/gif เท่านั้น")

    try:
        raw = base64.b64decode(payload, validate=True)
    except Exception:
        raise StorageError("ข้อมูลรูป (Base64) ไม่ถูกต้อง")
    if len(raw) == 0:
        raise StorageError("ไฟล์รูปว่างเปล่า")
    if len(raw) > MAX_BYTES:
        raise StorageError("ไฟล์รูปใหญ่เกิน 8MB — ย่อรูปก่อนส่ง")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{prefix}-{uuid.uuid4().hex[:12]}.{ext}"
    (UPLOAD_DIR / name).write_bytes(raw)
    return f"/uploads/{name}"
