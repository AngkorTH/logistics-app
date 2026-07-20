"""Pydantic schemas สำหรับชุดฟีเจอร์ฝั่งบริหาร (Management Suite)

ครอบคลุม: Smart Dispatch Queue, Penalty (หลายรายการ), User Management,
Monthly Trip History, Vehicle Assignment — ทั้งหมด Driver เข้าถึงไม่ได้
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Role, TripDifficulty, VehicleStatus


# --------------------------- Smart Dispatch Queue ---------------------------
class DispatchDriverOut(BaseModel):
    """คนขับ 1 คนในคิวจ่ายงาน พร้อม metric ที่ใช้เรียงลำดับ (กลุ่ม White)"""
    id: int
    emp_id: str
    name: str
    rating: int                       # Frontend เรนเดอร์เป็นดาว
    current_status: str               # WHITE / ORANGE / GREEN
    prev_difficulty: TripDifficulty | None = None  # ความยากทริปก่อนหน้า
    prev_load_seconds: float | None = None         # เวลา Orange→Green ทริปก่อน (วินาที)
    # ทริปที่กำลังวิ่งอยู่ (ORANGE/GREEN) — ใช้เปิด Trip Details modal ในหน้าจ่ายงาน
    active_trip_id: int | None = None
    active_trip_code: str | None = None
    plate: str | None = None          # เลขทะเบียนรถของทริปที่กำลังวิ่ง (ใช้ค้นหาด้วย)
    # เที่ยวหลักที่ยังไม่กด "จบเที่ยว" — มีค่าแม้คนขับพักเป็น WHITE ระหว่างขา
    main_trip_id: int | None = None
    main_trip_code: str | None = None
    legs_done: int = 0                # วิ่งไปแล้วกี่ขาในเที่ยวนี้
    legs_total: int = 0               # จ่ายงานย่อยไปทั้งหมดกี่ขา


class DispatchQueueOut(BaseModel):
    """คิวจ่ายงานจัดกลุ่มตามสถานะ 3 สี — White เรียงตาม Priority แล้ว"""
    white: list[DispatchDriverOut] = []   # รองาน (เรียงลำดับพร้อมจ่าย)
    orange: list[DispatchDriverOut] = []  # กำลังไปขึ้นของ
    green: list[DispatchDriverOut] = []   # กำลังไปส่ง


# --------------------------- Penalty (หลายรายการ) ---------------------------
class PenaltyCreate(BaseModel):
    amount: float = Field(..., gt=0)         # ยอดหักต้องมากกว่า 0
    reason: str = Field(..., min_length=1)   # บังคับเหตุผลเสมอ


class PenaltyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    trip_id: int
    driver_id: int
    amount: float
    reason: str
    creator_name: str
    created_at: datetime


class PenaltyListRow(PenaltyOut):
    """แถวในตารางสรุปหักเงิน (Dashboard) — เติมชื่อคนขับ + code ทริป"""
    driver_name: str
    trip_code: str


class DeductionLeaderRow(BaseModel):
    """แถวในตารางจัดอันดับการหักเงินรายเดือน (group by คนขับ) — task 3"""
    driver_id: int
    driver_name: str
    total_amount: float      # ยอดรวมเงินที่ถูกหักในเดือน/ปีนั้น
    count: int               # จำนวนครั้งที่ถูกหัก


# --------------------------- Notification (กล่องจดหมายบริหาร) ---------------------------
class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    at: datetime
    kind: str
    title: str
    message: str
    trip_id: int | None
    read: bool


# --------------------------- Audit Log (อ่าน) ---------------------------
class AuditLogOut(BaseModel):
    """แถวประวัติเหตุการณ์ (Audit Trail) — ใคร/ทำอะไร/ที่ไหน/เมื่อไหร่/รายละเอียด(เหตุผล)"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    at: datetime
    who: str
    action: str
    target: str
    detail: str


# --------------------------- User Management ---------------------------
class UserManageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    emp_id: str
    name: str
    phone: str
    role: Role
    active: bool
    notif: bool
    rating: int


class UserUpdate(BaseModel):
    """แก้ข้อมูลส่วนตัวพนักงาน (Admin+) — ส่งเฉพาะ field ที่ต้องการแก้"""
    name: str | None = Field(None, min_length=1)
    phone: str | None = Field(None, min_length=1)
    role: Role | None = None
    active: bool | None = None
    notif: bool | None = None


class RatingRequest(BaseModel):
    """ให้ดาวคนขับ 0-5 (Admin+)"""
    rating: int = Field(..., ge=0, le=5)


# --------------------------- Monthly Trip History ---------------------------
class MonthlyHistoryRow(BaseModel):
    month: str            # "2026-07"
    trips: int            # จำนวนทริปที่ปิดงานในเดือนนั้น
    total_distance: float
    total_allowance_net: float
    total_penalty: float


class SubTripRow(BaseModel):
    """งานย่อย (Sub-Trip/Drop) 1 ใบ ใต้เที่ยวหลัก — โชว์ 'ต้นทาง → ปลายทาง' ในประวัติ"""
    seq: int
    origin: str
    destination: str
    allowance: float
    delivered: bool
    delivered_at: str | None = None
    # URL รูปหลักฐานของขานี้ — เปิดดูย้อนหลังได้จากหน้าประวัติ
    loaded_photo: str | None = None   # ของที่ขนขึ้นรถ (ถ่ายตอนกดขนของเสร็จ)
    photo: str | None = None          # ส่งของสำเร็จ
    tarp: str | None = None           # ผ้าใบ


class TripHistoryRow(BaseModel):
    """แถวรายเที่ยวในตารางประวัติทริปรายเดือน (เมื่อเลือกเดือน/ปีแล้ว)"""
    trip_id: int
    code: str
    closed_at: str | None            # ISO datetime ของเวลาปิดงาน
    plate: str | None
    distance_km: float
    difficulty: TripDifficulty
    drops: int                       # จำนวนงานย่อย (Sub-Trips)
    sub_trips: list[SubTripRow] = []  # รายการงานย่อยเรียงตามลำดับ (กดดูรายละเอียดในหน้าประวัติ)
    allowance_net: float
    penalty: float


class MonthlyHistoryOut(BaseModel):
    driver_id: int
    driver_name: str
    months: list[MonthlyHistoryRow] = []
    # เติมเฉพาะเมื่อระบุ year+month (flow: เลือกคนขับ → เลือกเดือน/ปี → แสดงตาราง)
    trips: list[TripHistoryRow] = []


# --------------------------- Vehicle Assignment ---------------------------
class VehicleCreate(BaseModel):
    plate: str = Field(..., min_length=1)
    model: str = ""
    std_km_l: float = Field(3.5, gt=0)


class VehicleUpdate(BaseModel):
    model: str | None = None
    std_km_l: float | None = Field(None, gt=0)


class VehicleAssignRequest(BaseModel):
    """ผูก/ถอดคนขับประจำรถ — ส่ง null เพื่อถอด"""
    driver_id: int | None = None


class VehicleStatusRequest(BaseModel):
    """แอดมินสั่งเข้า/ออกจากการซ่อมด้วยมือ (Admin เท่านั้น — Supervisor ทำไม่ได้)

    reason บังคับเสมอ เพื่อบันทึกลง Audit ว่าใครสั่งซ่อมเพราะอะไร
    """
    status: VehicleStatus                    # MAINTENANCE = เข้าซ่อม · AVAILABLE = กลับมาพร้อมใช้
    reason: str = Field(..., min_length=1)
