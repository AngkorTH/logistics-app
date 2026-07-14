# Logistics ERP - Business Logic & State Machine

## 1. Driver State Machine (สถานะ 3 สี)
- **WHITE (รองาน):** สถานะเริ่มต้นเมื่อจบงานหรือไม่มีงาน
- **ORANGE (กำลังไปขึ้นของ):** เปลี่ยนอัตโนมัติเมื่อ Supervisor กด "จ่ายงาน" (พร้อมส่ง Push Notification ให้เตรียมคลุมผ้าใบ)
- **GREEN (กำลังไปส่ง):** เปลี่ยนเมื่อ Driver กด "ขนของขึ้นเสร็จแล้ว" (Soft Block: เปลี่ยนสถานะได้ทันทีโดยไม่ต้องรอรูปผ้าใบ)

## 2. Multi-Drop & Trip Loop Logic
- 1 ทริปหลัก (Main Trip) สามารถมีจุดส่งย่อย (Drops) ได้ 1-5 จุด 
- ตราบใดที่ยังส่งไม่ครบทุกจุดย่อย สถานะคนขับจะค้างอยู่ที่สี "GREEN"
- **การจบงาน:** คนขับต้องส่งรูป "ส่งของสำเร็จ" ให้ครบทุกจุด -> Supervisor ตรวจสอบและกดปิดงาน -> สถานะคนขับจะกลับเป็น "WHITE"

## 3. Evidence & Compliance (หลักฐานและการหักเงิน)
- **4 ปุ่มหลักฐานต่อ 1 จุดส่ง:** บิลน้ำมัน, บิลทางหลวง, รูปผ้าใบ, รูปส่งของสำเร็จ (ต้องแยกอัปโหลดรายจุดส่ง ไม่ให้เอกสารตีกัน)
- **Penalty Logic:** หากทำผิดกฎ Supervisor สามารถระบุยอดหักเงินได้ แต่ **"ต้องพิมพ์เหตุผลเสมอ"** - **การหักเงิน:** หักจาก "เบี้ยเลี้ยงรวมของทริปนั้น" เท่านั้น (ห้ามหักเข้าเนื้อค่าน้ำมันหรือเงินเดือน) และต้องส่งแจ้งเตือนให้ Admin ทราบ

## 4. Financial Freeze (ล็อกข้อมูลการเงิน)
- **Freeze on Close:** ทันทีที่ Supervisor กดปิดงาน ยอดเงินทั้งหมดของทริปนั้นจะถูกล็อก (Freeze) ถาวร
- **Request for Correction:** หากต้องการแก้ตัวเลขที่ล็อกแล้ว Supervisor ต้องกด "ขอปลดล็อก" พร้อมระบุเหตุผล ส่งให้ Super Admin เป็นผู้อนุมัติเท่านั้น

## 5. AI & Tracking Systems
- **AI OCR:** เมื่ออัปโหลดบิลน้ำมัน/ทางหลวง Backend ต้องดึงยอดเงินมาตั้งเป็นค่า Draft ให้ Supervisor ตรวจสอบก่อน (ห้าม Auto-commit)
- **GPS Geofencing:** บันทึกพิกัดอัตโนมัติเมื่อกด "ขนของขึ้นเสร็จแล้ว" และเมื่อส่งของสำเร็จในแต่ละจุด

## 6. Smart Dispatch & Management Logic (ห้าม Driver เข้าถึง)

### 6.1 Trip Difficulty & Driver Rating
- **Trip Difficulty:** ฟิลด์ `difficulty` บน Trip (`EASY`/`MEDIUM`/`HARD`) — Supervisor ตั้งตอนจ่ายงาน
- **Driver Rating:** ฟิลด์ `rating` บน User (0-5) — Admin/Super Admin ตั้ง Frontend แสดงเป็นดาวเท่านั้น

### 6.2 ตรรกะเรียงลำดับคนขับ (Driver Sorting)
API จ่ายงานคืนคนขับจัดกลุ่มตามสถานะทริปปัจจุบันเป็น 3 สี:
- **WHITE (รองาน):** พร้อมรับงาน — เรียงตาม Priority นี้ (ยาก→ง่าย = ควรได้พัก/งานเบา หรือกำหนดตาม policy):
  1. **ความยากทริปก่อนหน้า** (difficulty ของทริปล่าสุดที่ปิดแล้ว: HARD > MEDIUM > EASY)
  2. **ความไวกดขนของขึ้นเสร็จ** = `finished_loading_at − assigned_at` ของทริปก่อนหน้า (น้อย = ไว = ดีกว่า)
  3. **จำนวนดาว** มาก→น้อย
- **ORANGE (ไปขึ้นของ) / GREEN (ไปส่ง):** ติดงานอยู่ แสดงแยกกลุ่ม ไม่เข้าคิวจ่ายงาน
- คำนวณข้อมูลทริปก่อนหน้าจาก Trip ล่าสุด (`closed_at`/`status`) ของคนขับ ไม่ต้อง denormalize

### 6.3 Penalty (โมเดลใหม่ หลายรายการ)
- `Penalty(trip_id, driver_id, amount, reason, created_by, created_at)` — เก็บได้หลายบรรทัดต่อทริป/คนขับ
- Reason บังคับกรอกเสมอ · หักจากเบี้ยเลี้ยง (คงตรรกะ skill.md ข้อ 3) · ยังคงฟิลด์ `penalty` เดิมบน Trip ไว้เพื่อ backward-compat

### 6.4 RBAC ของ endpoint ชุดใหม่
| Endpoint | สิทธิ์ |
|---|---|
| จ่ายงาน / ตั้ง difficulty / dispatch queue | Supervisor+ |
| เพิ่ม Penalty | Supervisor+ |
| ให้ดาว (rating) | Admin+ |
| แก้ข้อมูลพนักงาน (user management) | Admin+ |
| ประวัติทริปรายเดือน | Supervisor+ |
| จัดการทะเบียนรถ / ผูกคนขับ | Admin+ |

> ⚠️ ทุก endpoint ข้างบน **Driver ต้องได้ 403** — ใช้ `require_supervisor` / `require_admin` เท่านั้น

## 7. Layout Refactor & Trip Adjustment Logic (Driver เข้าถึงไม่ได้)

### 7.1 Dashboard vs Dispatch vs Penalty (แยกหน้าชัดเจน)
- **Dashboard:** เหลือแค่ตัวเลขสรุป (รองาน/ขึ้นของ/ส่งของ/รอเช็กสลิป) — ไม่มีตารางทริป ไม่มีตารางหักเงิน
- **Dispatch Queue** คืน active trip ของแต่ละคนขับด้วย (`active_trip_id`, `active_trip_code`, `plate`) เพื่อเปิด Trip Details modal ได้ · รองรับ `?q=` ค้น "ชื่อคนขับ / เลขทะเบียน" (กรองทั้ง 3 กลุ่มสี, case-insensitive, substring)
- **Penalty history** `GET /penalties` รองรับ query: `driver_name` (substring), `month` (1-12), `year` (เช่น 2026) — กรองจาก `Penalty.created_at`

### 7.2 Trip Adjustment (`PATCH /trips/{id}/adjust`) — Supervisor+ (รวม Admin)
บังคับ `edit_reason` (min_length=1) ใน schema เสมอ ไม่ส่ง → 422 · ฟิลด์ที่แก้ได้ (ทุกฟิลด์ optional):
| field | กติกา |
|---|---|
| `distance_km` | ≥ 0 |
| `difficulty` | EASY/MEDIUM/HARD |
| `bonus` | ≥ 0 |
| `penalty` (+ `penalty_reason`) | ต้องมี `penalty_reason` · ห้ามหักเกินเบี้ยเลี้ยงรวม+โบนัส |
| `allowances` = `{drop_id: amount}` | drop ต้องอยู่ในทริปนี้ · amount ≥ 0 |

การ์ด: ทริป `frozen` แล้ว → 400 (ต้องขอ Correction ก่อน) · ทุกครั้งเขียน Audit 1 บรรทัด "แก้ไขข้อมูลทริป" ระบุ `edit_reason` + สรุป field ที่แก้

### 7.3 Monthly Trip History flow
`GET /users/{id}/history/monthly` — ไม่ส่ง param คืนสรุปรายเดือน (`months`) เหมือนเดิม · ส่ง `year` + `month` เพิ่ม → คืน `trips` (ตารางรายเที่ยวของเดือนนั้น: code, closed_at, distance, difficulty, drops, allowance_net, penalty, plate) สำหรับ flow เลือกคนขับ → เลือกเดือน/ปี → แสดงตาราง

## 8b. Auto-complete / Freeze / Unfreeze / Inbox (flow ใหม่)
- **จบงานอัตโนมัติ:** `record_delivery` เมื่อ drop สุดท้าย delivered ครบ → `_auto_complete` ตั้ง WHITE + `closed_at` (ยัง **ไม่ freeze**) + แจ้งเตือน `TRIP_DONE` · บังคับเฉพาะ "รูปส่งของสำเร็จ" (photo) รายจุด · บิลไม่บังคับ
- **ล็อกการเงิน (freeze):** `close_trip` = ปิดบัญชี → freeze snapshot · รับทริป GREEN หรือจบงานแล้ว (closed_at) · ทริป freeze = แก้ไม่ได้ (ดูอย่างเดียว)
- **ปลดล็อก (unfreeze):** `POST /trips/{id}/unfreeze` (Supervisor+) บังคับ `reason` → `frozen=False` (แก้ต่อได้) + Audit "ปลดล็อกการเงิน" + แจ้งเตือน `TRIP_UNFROZEN` · ต่างจาก correction (Super Admin อนุมัติ) — อันนี้ปลดเองได้แต่ทุกครั้งเด้งแจ้งเตือน
- **Inbox:** ตาราง `notifications` + `push_notification()` · `GET/POST /notifications` (Supervisor+) list/unread/read/read-all · kinds: BILL_UPLOADED / TRIP_DONE / TRIP_UNFROZEN · Frontend = กระดิ่งบน topbar (poll 20s)
- `TripOut` เพิ่ม `closed_at` เพื่อแยกทริปที่จบงานแล้วรอ "ล็อกการเงิน"

## 8. Manual Override / OCR Edit / Leaderboard / Audit (Driver เข้าไม่ได้)

### 8.1 Manual Status Override (task 1)
`POST /trips/{id}/override-status` — Supervisor+ · body `{ status: WHITE|ORANGE|GREEN, reason }` (reason บังคับ)
- `override_status()` ใน state_machine: ตั้ง `trip.status` ตรงๆ + `override=True` · เติม `assigned_at`/`finished_loading_at`/`closed_at` ถ้ายังว่าง · frozen → 400 · status เดิม → 400
- แจ้งเตือนคนขับผ่าน `_notify_status_change` (stub) + Audit "เปลี่ยนสถานะ (Manual Override)"

### 8.2 Manual Edit OCR Amount (task 2)
`PATCH /receipts/{id}/amount` — Supervisor+ · body `{ new_amount≥0, reason }` (บังคับทั้งคู่ · schema 422 ถ้าขาด)
- `edit_receipt_amount()`: guard not frozen · แก้ `receipt.amount` (คง approved เดิม) · Audit "แก้ยอดเงินใบเสร็จ (OCR)" เก็บ ยอดเดิม→ใหม่ + เหตุผล

### 8.3 Deduction Leaderboard (task 3)
`GET /penalties/leaderboard?month=&year=` — Supervisor+ · `deduction_leaderboard()` group by `Penalty.driver_id` → `sum(amount)` + `count(id)` เรียง `sum desc` · กรองจาก `Penalty.created_at`
> route นี้ประกาศ **ก่อน** `/penalties` เพื่อไม่ให้ path ชนกัน

### 8.4 ปุ่ม "ยืนยันยอด" (task 4)
Bug เดิม: ใช้ `window.prompt` (ถูกบล็อกใน sandbox/embedded → กดไม่ติด) · Fix: ใช้ `ReceiptAmountModal` (mode `approve`/`edit`) แทน · approve เรียก `POST /receipts/{id}/approve` เหมือนเดิม UI อัปเดตทันทีผ่าน invalidate `['trips']`

### 8.5 Audit Log read (task 5)
`GET /audit-logs?action=&target=&limit=` — **Admin+ (require_admin)** · อ่านตาราง `audit_logs` (model + `write_audit` มีอยู่แล้ว ไม่ต้อง migrate) · filter substring บน action/target · เรียง `at desc` · schema `AuditLogOut`
- Frontend `/admin-audit-log` (roles ADM) แสดงตาราง + ปุ่มกรองด่วนตาม action