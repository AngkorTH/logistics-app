"""ตั้งค่า logging ของแอป — ปลอดภัยกับข้อความภาษาไทยทุก console

ปัญหาที่แก้: `print()` ข้อความไทย/สัญลักษณ์ (เช่น →) ระเบิดด้วย UnicodeEncodeError
เมื่อ stdout ไม่ใช่ UTF-8 (console Windows ดีฟอลต์เป็น cp1252) ทำให้ request
ที่แค่ "แจ้งเตือน" พังยกใบเป็น HTTP 500 ทั้งที่ธุรกรรมหลักสำเร็จไปแล้ว

วิธีแก้ 2 ชั้น:
1. บังคับ stdout/stderr เป็น UTF-8 (errors="replace" กันพังต่อให้เทอร์มินัลไม่รองรับ)
2. ใช้ logging แทน print — ถ้า handler พัง logging กลืน exception ให้เอง
   ไม่ลามออกมาทำ request ล้ม
"""
import logging
import sys

_CONFIGURED = False


def setup_logging(level: int = logging.INFO) -> None:
    """เรียกครั้งเดียวตอน start แอป (idempotent)"""
    global _CONFIGURED
    if _CONFIGURED:
        return

    # ชั้นที่ 1: console ที่ไม่ใช่ UTF-8 (Windows cp1252) ต้องไม่ทำให้ข้อความไทยพัง
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass  # stream ที่ reconfigure ไม่ได้ (เช่นถูก redirect) — ข้ามไป

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))

    root = logging.getLogger("app")
    root.setLevel(level)
    root.handlers = [handler]
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """logger ของโมดูล — ชื่อขึ้นต้นด้วย 'app.' เสมอเพื่อใช้ config เดียวกัน"""
    setup_logging()
    return logging.getLogger(f"app.{name}")
