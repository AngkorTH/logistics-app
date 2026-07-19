"""Enum กลางของระบบ — ใช้ str-Enum เพื่อให้ค่าใน DB อ่านออกและ serialize เป็น JSON ได้ตรงๆ"""
import enum


class Role(str, enum.Enum):
    DRIVER = "DRIVER"           # พนักงานขับรถ — เห็นเฉพาะทริปตัวเอง
    SUPERVISOR = "SUPERVISOR"   # คนคุมงาน
    ADMIN = "ADMIN"             # แอดมิน
    SUPER_ADMIN = "SUPER_ADMIN" # ซุปเปอร์แอดมิน — อนุมัติปลดล็อกการเงิน


class TripStatus(str, enum.Enum):
    WHITE = "WHITE"     # รองาน (เริ่มต้น/จบงาน)
    ORANGE = "ORANGE"   # กำลังไปขึ้นของ (Supervisor จ่ายงานแล้ว)
    GREEN = "GREEN"     # กำลังไปส่ง (คนขับกดขนของขึ้นเสร็จ)


class TripDifficulty(str, enum.Enum):
    EASY = "EASY"       # ง่าย
    MEDIUM = "MEDIUM"   # ปานกลาง
    HARD = "HARD"       # ยาก


# เปอร์เซ็นต์เบี้ยเลี้ยงตามความยาก — เบี้ยเลี้ยงต่อขา = รายได้ต่อขา × เปอร์เซ็นต์นี้
ALLOWANCE_RATE = {
    TripDifficulty.EASY: 0.05,    # ง่าย 5%
    TripDifficulty.MEDIUM: 0.07,  # ปานกลาง 7%
    TripDifficulty.HARD: 0.10,    # ยาก 10%
}


def compute_allowance(revenue: float, difficulty: TripDifficulty) -> float:
    """เบี้ยเลี้ยงของขา 1 ใบ — ปัดทศนิยม 2 ตำแหน่ง"""
    return round((revenue or 0.0) * ALLOWANCE_RATE[difficulty], 2)


class ReceiptKind(str, enum.Enum):
    FUEL = "FUEL"   # บิลน้ำมัน
    TOLL = "TOLL"   # บิลทางหลวง


class CorrectionStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class InspectionStatus(str, enum.Enum):
    PASSED = "PASSED"                   # ติ๊กผ่านทุกข้อ — เริ่มงานได้ทันที
    PENDING_REVIEW = "PENDING_REVIEW"   # มีจุดชำรุด — รอคุมงาน/แอดมินประเมิน
    APPROVED = "APPROVED"               # ประเมินแล้ว อนุญาตให้วิ่งได้
    REJECTED = "REJECTED"               # ประเมินแล้ว ห้ามวิ่ง (รถต้องซ่อม)


class AdvanceStatus(str, enum.Enum):
    PENDING = "PENDING"     # รออนุมัติ
    APPROVED = "APPROVED"   # อนุมัติแล้ว — รอหักตอนปิดทริป
    REJECTED = "REJECTED"


class IncidentKind(str, enum.Enum):
    BREAKDOWN = "BREAKDOWN"   # รถเสีย/ขัดข้อง
    ACCIDENT = "ACCIDENT"     # อุบัติเหตุ
    OTHER = "OTHER"


class IncidentStatus(str, enum.Enum):
    OPEN = "OPEN"           # เปิดเหตุอยู่ — ทริปถูก pause
    RESOLVED = "RESOLVED"   # ปิดเหตุแล้ว — ทริปวิ่งต่อได้


class GpsEvent(str, enum.Enum):
    LOADED = "LOADED"        # กด "ขนของขึ้นเสร็จ" — geo-stamp ต้นทาง
    DELIVERED = "DELIVERED"  # ส่งของสำเร็จรายจุด — geo-stamp ปลายทาง


class VehicleStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"      # พร้อมใช้งาน — จ่ายงานได้
    MAINTENANCE = "MAINTENANCE"  # กำลังซ่อม — ล็อกไม่ให้จ่ายงาน (คนขับแจ้งเหตุรถมีปัญหา)
