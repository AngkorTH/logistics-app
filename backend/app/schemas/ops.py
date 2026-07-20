"""Pydantic schemas สำหรับ Trip / Evidence / Finance / Correction endpoints

รวมไว้ที่เดียวเพราะ business object ผูกกันแน่น (ทริป → จุดส่ง → บิล → การเงิน → correction)
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    AdvanceStatus,
    Role,
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
    liters: float = 0          # จำนวนลิตรที่เติม (บิลน้ำมัน)
    date: str | None
    approved: bool
    photo: str | None = None   # URL รูปใบเสร็จจริง (Phase 4)


class DropOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    seq: int
    name: str
    origin: str             # ต้นทางของงานย่อย เช่น "ลำปาง" (ห้ามว่าง — บังคับที่ DB ด้วย)
    destination: str        # ปลายทางของงานย่อย เช่น "กรุงเทพ" (ห้ามว่าง)
    revenue: float = 0                                   # รายได้ของขานี้ (ฐานคิดเบี้ยเลี้ยง)
    difficulty: TripDifficulty = TripDifficulty.MEDIUM   # ความยากรายขา
    allowance: float                                     # = revenue × %ความยาก
    delivered: bool
    loaded_photo: str | None = None  # URL รูปของที่ขนขึ้นรถ (ถ่ายตอนกดขนของเสร็จ)
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
    completed_at: datetime | None = None  # Supervisor กด "จบเที่ยว" แล้ว (None = เที่ยวหลักยัง Active)
    odometer_start: float | None = None  # เลขไมล์เริ่ม (คนขับกรอกตอนเริ่มงาน)
    odometer_start_photo: str | None = None  # URL รูปหน้าปัดไมล์ตอนเริ่มงาน
    odometer_end: float | None = None    # เลขไมล์จบ (ส่งตอนจบงาน)
    odometer_end_photo: str | None = None  # URL รูปหน้าปัดไมล์ตอนจบงาน
    km_per_liter: float | None = None    # อัตราสิ้นเปลือง กม./ลิตร (None = คิดไม่ได้)
    drops: list[DropOut] = []
    trip_receipts: list[ReceiptOut] = []  # บิลเติมน้ำมันระหว่างทาง (ไม่ผูกจุดส่ง)


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


class RouteLegOut(BaseModel):
    """1 ขาในเส้นทางของเที่ยว — เช่น "1. ลำปาง ไป กรุงเทพฯ" """
    seq: int
    origin: str
    destination: str
    delivered: bool
    allowance: float


class TripSummaryOut(BaseModel):
    """สรุปรวบยอดทั้งเที่ยว — โชว์ตอนกด "จบเที่ยว" และในประวัติทริป"""
    legs: int                            # วิ่งไปแล้วกี่ขา (ส่งสำเร็จ)
    legs_total: int                      # จ่ายงานย่อยไปทั้งหมดกี่ขา
    fuel_liters: float                   # น้ำมันรวมทั้งเที่ยว (ลิตร)
    fuel_cost: float                     # ค่าน้ำมันรวม (บิลที่อนุมัติแล้ว)
    toll_cost: float
    odometer_start: float | None = None  # เลขไมล์ต้นเที่ยว
    odometer_end: float | None = None    # เลขไมล์ปลายเที่ยว
    total_km: float                      # ระยะทางรวมทั้งเที่ยว
    km_per_liter: float | None = None
    route: list[RouteLegOut] = []        # เส้นทางเรียงลำดับเป็นข้อๆ


class TripDetailOut(TripOut):
    """ทริป + สรุปการเงิน + สรุปรวบยอดทั้งเที่ยว สำหรับหน้ารายละเอียด"""
    finance: FinanceOut
    summary: TripSummaryOut


# --------------------------- Trip create (ฟอร์มจ่ายงาน) ---------------------------
class DropCreate(BaseModel):
    """งานย่อย 1 ใบ — **บังคับกรอกต้นทาง + ปลายทาง + รายได้ต่อขา**

    name เว้นว่างได้ ระบบจะตั้งเป็น "ต้นทาง → ปลายทาง" ให้เอง
    เบี้ยเลี้ยงไม่รับจากผู้ใช้ — ระบบคิดเอง = รายได้ต่อขา × เปอร์เซ็นต์ความยาก
    """
    origin: str = Field(..., min_length=1)       # เริ่มจากไหน
    destination: str = Field(..., min_length=1)  # ไปส่งที่ไหน
    revenue: float = Field(..., gt=0)            # รายได้ต่อขา (บังคับ) — ฐานคิดเบี้ยเลี้ยง
    difficulty: TripDifficulty | None = None     # ไม่ส่ง = ใช้ความยากของทริป
    name: str = ""

    @field_validator("origin", "destination")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        """เว้นวรรคล้วน (" ") ผ่าน min_length ได้ — ต้อง trim แล้วเช็กซ้ำถึงจะกันได้จริง"""
        if not v.strip():
            raise ValueError("ต้องกรอกทั้งต้นทางและปลายทาง — เว้นว่างไม่ได้")
        return v.strip()

    def label(self) -> str:
        return self.name.strip() or f"{self.origin.strip()} → {self.destination.strip()}"


class TripCreate(BaseModel):
    driver_id: int
    distance_km: float = Field(0, ge=0)
    # Multi-Drop: 1-5 จุดต่อทริป (skill.md ข้อ 2)
    drops: list[DropCreate] = Field(..., min_length=1, max_length=5)


class DropAddRequest(DropCreate):
    """เพิ่มงานย่อย (Sub-Trip) เข้าไปในทริปเดิมที่ยัง Active — ต้นทาง/ปลายทางบังคับเหมือนกัน"""


class CompleteTripRequest(BaseModel):
    """Supervisor กด "จบเที่ยว" — ยังส่งงานย่อยไม่ครบ → 409 ให้ยืนยันแล้วส่ง force=True"""
    force: bool = False


class DriverPickOut(BaseModel):
    """คนขับที่ "รองาน" (สีขาว) 1 คน สำหรับฟอร์มจ่ายงาน

    waiting_type แยก 2 ประเภท:
    - SUB_TRIP  = ว่าง แต่ยังมีเที่ยวหลักค้าง (ยังไม่กดจบเที่ยว) → "ยังไม่จบเที่ยว รองานย่อย"
    - NEW_TRIP  = ว่าง และไม่มีเที่ยวหลักค้างเลย → "จบเที่ยวแล้ว รองานใหม่"
    """
    model_config = ConfigDict(from_attributes=True)
    id: int
    emp_id: str
    name: str
    phone: str
    role: Role
    active: bool
    notif: bool
    waiting_type: str                    # SUB_TRIP | NEW_TRIP
    active_trip_id: int | None = None    # เที่ยวหลักที่ยัง Active (ถ้ามี)
    active_trip_code: str | None = None
    active_trip_drops: int = 0           # จำนวนงานย่อยที่มีอยู่ในเที่ยวนั้น


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
    # หมายเหตุ: เลขไมล์เริ่มไม่รับตรงนี้แล้ว — คนขับกรอกเองตอนกด "เริ่มงาน" พร้อมรูปหน้าปัด


class GeoRequest(BaseModel):
    """พิกัด GPS ที่แนบมาตอนกดขนของเสร็จ / ส่งของสำเร็จ

    captured_at = เวลาที่คนขับ "กดปุ่มจริง" (Offline Auto-Sync ข้อ 1.1) —
    ตอนออฟไลน์ client เก็บคิวไว้แล้วค่อยส่ง เวลาต้องเป็นตอนกด ไม่ใช่ตอนเน็ตกลับ"""
    lat: float
    lng: float
    force: bool = False
    captured_at: datetime | None = None
    photo_b64: str | None = None   # รูปหลักฐาน (Phase 4) — ใช้กับ endpoint ส่งของสำเร็จ


class StartTripRequest(GeoRequest):
    """เริ่มงาน (ขนของขึ้นเสร็จ) — เลขไมล์เริ่ม/รูปหน้าปัดถูกบันทึกไปแล้วตอนส่งผลตรวจสภาพรถ
    ส่งซ้ำได้ (optional) เพื่อแก้ค่า · ไม่ส่ง = ใช้ค่าที่บันทึกไว้ · ทริปที่ยังไม่มีค่า = เริ่มงานไม่ได้

    **loaded_photo_b64 บังคับ** — รูปของที่ขนขึ้นรถแล้ว (ถ่ายในหน้ายืนยันก่อนเปลี่ยนเป็นสีเขียว)
    """
    odometer_start: float | None = Field(None, ge=0)
    odometer_photo_b64: str | None = None
    loaded_photo_b64: str = Field(..., min_length=1)


# --------------------------- Evidence ---------------------------
class ReceiptUploadRequest(BaseModel):
    """คนขับอัปรูปบิล — **ไม่มี OCR แล้ว** (ปิดการอ่านยอด/วันที่อัตโนมัติ)

    คนขับส่งได้แค่ "รูปบิล" (บังคับ) · ยอดเงินและวันที่บนบิลเป็น 0/None เสมอ
    รอ Supervisor เปิดรูปดูแล้วพิมพ์เองตอนยืนยัน (ดู ReceiptApproveRequest)
    """
    kind: ReceiptKind
    photo_b64: str = Field(..., min_length=1)  # รูปถ่ายใบเสร็จจริง (บังคับ — ไม่มีรูป = ตรวจไม่ได้)
    captured_at: datetime | None = None  # เวลาอัปโหลดจริงตอนออฟไลน์ (Offline Auto-Sync)
    liters: float | None = Field(None, ge=0)  # จำนวนลิตร (บิลน้ำมัน) — ใช้คิด km/L


class FuelLogRequest(BaseModel):
    """แจ้งเติมน้ำมันระหว่างทริป — รูปสลิป (Base64) + จำนวนลิตร (บังคับทั้งคู่)

    ยอดเงินไม่รับจากคนขับแล้ว (ปิด OCR) — Supervisor กรอกเองตอนยืนยันบิล
    """
    photo_b64: str = Field(..., min_length=1)   # รูปสลิปน้ำมัน
    liters: float = Field(..., gt=0)            # จำนวนลิตรที่เติม
    captured_at: datetime | None = None         # เวลาเติมจริงตอนออฟไลน์


class TripReceiptRequest(BaseModel):
    """อัปบิลระหว่างทาง (Mid-Trip) — ใช้ได้ตลอดเวลาที่คนขับยังวิ่งงานอยู่ (🟠 และ 🟢)

    ต่างจากบิลรายจุดส่ง (/drops/{id}/receipt) ที่ 1 จุดมีได้อย่างละ 1 ใบ:
    ใบพวกนี้ผูกกับ "ทริป" ตรงๆ อัปกี่ใบก็ได้ ไม่ชนกัน
    (แวะปั๊ม → ถ่ายสลิปส่งเลย ไม่ต้องรอส่งของเสร็จ)

    ยอดเงิน/วันที่ไม่รับจากคนขับ (ปิด OCR) — Supervisor เปิดรูปแล้วคีย์เองตอนยืนยัน
    """
    kind: ReceiptKind                            # FUEL (น้ำมัน) หรือ TOLL (ทางหลวง)
    photo_b64: str = Field(..., min_length=1)    # รูปบิล/สลิป (บังคับ)
    liters: float | None = Field(None, gt=0)     # จำนวนลิตร — บังคับเฉพาะบิลน้ำมัน
    captured_at: datetime | None = None          # เวลาที่กดจริงตอนออฟไลน์


class EndTripRequest(BaseModel):
    """จบงาน — ส่งเลขไมล์จบ + **รูปหน้าปัดไมล์ (บังคับ)** เพื่อคิดระยะทางและ km/L

    รูปหน้าปัดตอนจบเป็นหลักฐานคู่กับเลขที่คนขับพิมพ์ (ไว้ให้แอดมินเทียบย้อนหลัง)
    ขาดรูป = ส่งจบงานไม่ได้ (422 ตั้งแต่ schema)
    """
    odometer_end: float = Field(..., ge=0)
    odometer_photo_b64: str = Field(..., min_length=1)  # รูปหน้าปัดไมล์ตอนจบ (บังคับ)
    force: bool = False                          # ยืนยันเมื่อยังส่งของไม่ครบ


class TarpUploadRequest(BaseModel):
    """อัปรูปผ้าใบ — บังคับแนบรูปจริง (เก็บ URL ไฟล์ลง DB ไม่ใช่ธง boolean)"""
    photo_b64: str = Field(..., min_length=1)
    captured_at: datetime | None = None


class DeliveryRequest(GeoRequest):
    """ส่งของสำเร็จ 1 จุด — บังคับแนบรูปหลักฐานจริงคู่กับพิกัดปลายทาง"""
    photo_b64: str = Field(..., min_length=1)


class ReceiptApproveRequest(BaseModel):
    """Supervisor เปิดรูปบิลดู แล้ว **พิมพ์ยอดเงิน + วันที่เอง** (แทน OCR)

    บังคับทั้งคู่ — ปล่อยว่างไม่ได้ เพราะไม่มีค่าจาก OCR มาให้เป็น default อีกแล้ว
    """
    amount: float = Field(..., ge=0)          # ยอดเงินบนบิล (คนกรอกเอง)
    date: str = Field(..., min_length=1)      # วันที่บนบิล (คนกรอกเอง) เช่น "2026-07-19"


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
    """คนขับส่งผล checklist ตรวจสภาพรถ — key อิสระ เช่น {"tires": true, "lights": false}

    บังคับแนบเลขไมล์เริ่ม + รูปหน้าปัดไมล์มาด้วยเสมอ (ด่านเดียวกับปุ่ม "ส่งผลตรวจ" ฝั่ง UI)
    """
    items: dict[str, bool] = Field(..., min_length=1)
    odometer_start: float = Field(..., ge=0)            # เลขไมล์ตอนเริ่ม (บังคับ)
    odometer_photo_b64: str = Field(..., min_length=1)  # รูปหน้าปัดไมล์ Base64 (บังคับ)
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
