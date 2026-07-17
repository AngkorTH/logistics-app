"""Pydantic schemas สำหรับ Trip / Evidence / Finance / Correction endpoints

รวมไว้ที่เดียวเพราะ business object ผูกกันแน่น (ทริป → จุดส่ง → บิล → การเงิน → correction)
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    AdvanceStatus,
    CorrectionStatus,
    IncidentKind,
    IncidentStatus,
    InspectionStatus,
    ReceiptKind,
    TripDifficulty,
    TripStatus,
    VehicleStatus,
)


# --------------------------- Trip / Drop read ---------------------------
class ReceiptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: ReceiptKind
    amount: float
    date: str | None
    approved: bool
    photo: str | None = None   # URL รูปใบเสร็จจริง (Phase 4)


class DropOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    seq: int
    name: str
    allowance: float
    delivered: bool
    photo: str | None = None   # URL รูปส่งของสำเร็จ (Phase 4) — None = ยังไม่มี
    tarp: str | None = None    # URL รูปผ้าใบ
    gps: str | None
    receipts: list[ReceiptOut] = []


class TripOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    driver_id: int
    plate: str | None
    distance_km: float
    status: TripStatus
    difficulty: TripDifficulty
    bonus: float
    penalty: float
    penalty_reason: str
    frozen: bool
    override: bool
    paused: bool = False                # มีเหตุ SOS ค้าง — ทริปถูกพักชั่วคราว
    closed_at: datetime | None = None   # จบงานแล้ว (delivered) — ใช้แยกทริปที่รอ "ล็อกการเงิน"
    drops: list[DropOut] = []


class FinanceOut(BaseModel):
    """สรุปการเงินของทริป (คิดสดจาก service.compute_finance)"""
    allowance_total: float
    bonus: float
    penalty: float
    allowance_net: float
    fuel_total: float
    toll_total: float
    advance_total: float   # ยอดเบิกล่วงหน้าที่หัก/รอหักกับทริปนี้
    payout_net: float      # ยอดจ่ายสุทธิหลังหักเบิกล่วงหน้า


class TripDetailOut(TripOut):
    """ทริป + สรุปการเงินในก้อนเดียว สำหรับหน้ารายละเอียด"""
    finance: FinanceOut


# --------------------------- Trip create (ฟอร์มจ่ายงาน) ---------------------------
class DropCreate(BaseModel):
    name: str = Field(..., min_length=1)
    allowance: float = Field(0, ge=0)


class TripCreate(BaseModel):
    driver_id: int
    distance_km: float = Field(0, ge=0)
    # Multi-Drop: 1-5 จุดต่อทริป (skill.md ข้อ 2)
    drops: list[DropCreate] = Field(..., min_length=1, max_length=5)


class VehicleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    plate: str
    model: str
    driver_id: int | None
    status: VehicleStatus = VehicleStatus.AVAILABLE   # AVAILABLE / MAINTENANCE


# --------------------------- State machine ---------------------------
class AssignRequest(BaseModel):
    """จ่ายงาน — ไม่ต้องส่งทะเบียนรถแล้ว (ข้อ 2.1):
    ระบบดึงทะเบียนอัตโนมัติจากคลังรถยนต์ที่ผูกกับคนขับของทริป"""
    difficulty: TripDifficulty = TripDifficulty.MEDIUM  # Supervisor เลือกความยากทริป
    force: bool = False


class GeoRequest(BaseModel):
    """พิกัด GPS ที่แนบมาตอนกดขนของเสร็จ / ส่งของสำเร็จ

    captured_at = เวลาที่คนขับ "กดปุ่มจริง" (Offline Auto-Sync ข้อ 1.1) —
    ตอนออฟไลน์ client เก็บคิวไว้แล้วค่อยส่ง เวลาต้องเป็นตอนกด ไม่ใช่ตอนเน็ตกลับ"""
    lat: float
    lng: float
    force: bool = False
    captured_at: datetime | None = None
    photo_b64: str | None = None   # รูปหลักฐาน (Phase 4) — ใช้กับ endpoint ส่งของสำเร็จ


# --------------------------- Evidence ---------------------------
class ReceiptUploadRequest(BaseModel):
    kind: ReceiptKind
    ocr_amount: float | None = None  # ผลอ่าน OCR (จำลอง) — ตั้งเป็น draft
    ocr_date: str | None = None
    captured_at: datetime | None = None  # เวลาอัปโหลดจริงตอนออฟไลน์ (Offline Auto-Sync)
    photo_b64: str | None = None         # รูปถ่ายใบเสร็จจริง (Phase 4)


class TarpUploadRequest(BaseModel):
    """อัปรูปผ้าใบ (Phase 4) — body ทั้งก้อน optional เพื่อ backward-compat"""
    photo_b64: str | None = None
    captured_at: datetime | None = None


class ReceiptApproveRequest(BaseModel):
    amount: float | None = None  # แก้ยอดก่อนอนุมัติได้


class ReceiptEditRequest(BaseModel):
    """แก้ยอดเงินใบเสร็จ OCR (Supervisor+) — บังคับส่งยอดใหม่ + เหตุผลเสมอ (task 2)"""
    new_amount: float = Field(..., ge=0)          # ยอดเงินใหม่ (บังคับ)
    reason: str = Field(..., min_length=1)        # เหตุผลการแก้ไข (บังคับ) → ลง Audit


class StatusOverrideRequest(BaseModel):
    """เปลี่ยนสถานะทริปแบบ Manual โดย Supervisor/Admin — บังคับเหตุผล (task 1)"""
    status: TripStatus                            # สถานะเป้าหมาย WHITE/ORANGE/GREEN
    reason: str = Field(..., min_length=1)        # เหตุผล → ลง Audit + แจ้งเตือนคนขับ


class UnfreezeRequest(BaseModel):
    """ปลดล็อกการเงินทริปที่ freeze แล้ว เพื่อกลับมาแก้ไข — บังคับเหตุผล + เด้งแจ้งเตือน"""
    reason: str = Field(..., min_length=1)


# --------------------------- Pre-trip Inspection ---------------------------
class InspectionSubmitRequest(BaseModel):
    """คนขับส่งผล checklist ตรวจสภาพรถ — key อิสระ เช่น {"tires": true, "lights": false}"""
    items: dict[str, bool] = Field(..., min_length=1)
    defect_note: str = ""
    defect_photo_b64: str | None = None   # รูปจุดชำรุด Base64 (บังคับเมื่อมีข้อไม่ผ่าน)


class InspectionReviewRequest(BaseModel):
    """คุมงาน/แอดมินประเมินจุดชำรุด"""
    approve: bool
    note: str = ""


class InspectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    trip_id: int
    driver_id: int
    items: str            # JSON string ของ checklist
    passed: bool
    defect_note: str
    defect_photo: str | None   # URL รูปจุดชำรุด (Phase 4)
    status: InspectionStatus
    reviewer_name: str
    created_at: datetime


# --------------------------- SOS / Incident ---------------------------
class SosRequest(BaseModel):
    """คนขับแจ้งเหตุฉุกเฉินระหว่างทริป — แนบพิกัด + รูปหน้างาน"""
    kind: IncidentKind = IncidentKind.BREAKDOWN
    message: str = ""
    lat: float | None = None
    lng: float | None = None
    photo_b64: str | None = None   # รูปหน้างาน Base64 (Phase 4)
    captured_at: datetime | None = None  # เวลากดแจ้งเหตุจริงตอนออฟไลน์


class IncidentResolveRequest(BaseModel):
    note: str = ""


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    trip_id: int
    driver_id: int
    kind: IncidentKind
    message: str
    gps: str | None
    photo: str | None   # URL รูปหน้างาน (Phase 4)
    status: IncidentStatus
    resolver_name: str
    created_at: datetime


# --------------------------- Maintenance Report (แจ้งเหตุ/รถมีปัญหา ตอนรองาน) ---------------------------
class MaintenanceReportRequest(BaseModel):
    """คนขับแจ้งเหตุรถมีปัญหา — บังคับรายละเอียด + รูปหลักฐาน"""
    message: str = Field(..., min_length=1)        # รายละเอียดปัญหา (บังคับ)
    photo_b64: str = Field(..., min_length=1)      # รูปหลักฐาน Base64 (บังคับ)
    captured_at: datetime | None = None            # เวลากดแจ้งจริงตอนออฟไลน์


class MaintenanceResolveRequest(BaseModel):
    note: str = ""


class MaintenanceReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    driver_id: int
    vehicle_id: int | None
    plate: str
    message: str
    photo: str | None
    status: IncidentStatus
    resolver_name: str
    created_at: datetime


# --------------------------- Advance Payment ---------------------------
class AdvanceCreateRequest(BaseModel):
    """คนขับขอเบิกเงินล่วงหน้า — ยอด + เหตุผล (บังคับ)"""
    amount: float = Field(..., gt=0)
    reason: str = Field(..., min_length=1)


class AdvanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    driver_id: int
    trip_id: int | None
    amount: float
    reason: str
    status: AdvanceStatus
    requested_at: datetime
    decider_name: str
    deducted_trip_id: int | None


# --------------------------- Finance ---------------------------
class PenaltyRequest(BaseModel):
    amount: float
    reason: str = Field(..., min_length=1)  # บังคับใส่เหตุผลเสมอ


class BonusRequest(BaseModel):
    amount: float


# --------------------------- Trip Adjustment (แก้ข้อมูลทริป + เหตุผล) ---------------------------
class TripAdjustRequest(BaseModel):
    """แก้ข้อมูลทริปแบบรวม (Supervisor+/Admin) — ทุก field เป็น optional
    ยกเว้น edit_reason ที่ **บังคับเสมอ** เพื่อบันทึกลง Audit Trail (claude.md ข้อ 6.5)
    """
    edit_reason: str = Field(..., min_length=1)          # เหตุผลการแก้ไข — บังคับ
    distance_km: float | None = Field(None, ge=0)
    difficulty: TripDifficulty | None = None
    bonus: float | None = Field(None, ge=0)
    penalty: float | None = Field(None, ge=0)
    penalty_reason: str | None = None                    # ต้องมีเมื่อแก้ penalty
    allowances: dict[int, float] | None = None           # {drop_id: allowance ใหม่}


# --------------------------- Correction ---------------------------
class CorrectionRequest(BaseModel):
    field_key: str  # fuel / toll / bonus / penalty / allowance:<dropId>
    new_val: float
    reason: str = Field(..., min_length=1)


class RejectRequest(BaseModel):
    reason: str = ""


class CorrectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    trip_id: int
    requester_name: str
    field_key: str
    field_label: str
    old_val: float
    new_val: float
    reason: str
    status: CorrectionStatus
