# Logistics ERP - Project Architecture & Core Guidelines

## 1. Tech Stack Overview
- **Frontend:** React (Vite) + Tailwind CSS (อ้างอิง UI/UX จากไฟล์ prototype-ui.tsx.html)
- **Backend:** Python (FastAPI หรือ Flask) สำหรับประมวลผล Business Logic, AI OCR และ GPS
- **Database:** PostgreSQL (หรือตามที่ผู้ใช้กำหนด)

## 2. User Roles & Permissions
ระบบแบ่งผู้ใช้งานเป็น 3 ระดับอย่างเข้มงวด:
- **Driver (พนักงานขับรถ):** Mobile-First UI มองเห็นและจัดการได้เฉพาะทริปของตนเองเท่านั้น
- **Supervisor (คนคุมงาน):** Desktop/Tablet UI จัดการงาน ตรวจหลักฐาน และดูแลยอดหักเงิน
- **Admin / Super Admin:** เข้าถึงได้ทุกเพจ จัดการบัญชี ทะเบียนรถ และอนุมัติการปลดล็อกข้อมูลการเงิน (Request for Correction)

## 3. Security & Audit Guidelines
- **Single Session Lock:** 1 บัญชีเข้าได้ 1 อุปกรณ์ หากเข้าซ้อนให้ดีดเครื่องเก่าออกทันที
- **Audit Trail (System Logs):** ทุกการกระทำที่สำคัญ (จ่ายงาน, เปลี่ยนสถานะ, คีย์เงิน, หักเงิน) ต้องถูกบันทึกลง Log โดยระบุ: "ใคร ทำอะไร ข้อมูลไหน เวลาใด"
- **API Security:** Backend ต้องตรวจสอบ Token เสมอ เพื่อป้องกันไม่ให้ Driver ดึงข้อมูลของทริปที่ไม่ใช่ของตนเอง

## 4. Coding Standards (Python Backend)
- เขียนโค้ด Backend ด้วย Python ระดับ Intermediate
- ให้เขียน Comment สรุปอธิบายการทำงานของฟังก์ชันที่ซับซ้อน (เช่น ระบบคำนวณเงิน หรือระบบเปลี่ยนสถานะ) เป็นภาษาไทย เพื่อให้นักพัฒนาดูแลต่อได้ง่าย

## 5. Management Suite (ฟีเจอร์ฝั่งบริหาร — ห้าม Driver เข้าถึงเด็ดขาด)
ระบบชุดนี้ทั้งหมด **Driver มองไม่เห็นและเรียก API ไม่ได้** ทั้งระดับ API และ UI จำกัดเฉพาะ Supervisor / Admin / Super Admin ตามที่ระบุ:

- **Smart Dispatch Queue (จ่ายงานอัจฉริยะ):** Supervisor เลือก "ความยากทริป" (Easy/Medium/Hard) ตอนจ่ายงาน · API จัดลำดับคนขับจัดกลุ่มตามสถานะ 3 สี (White/Orange/Green) · กลุ่ม White เรียงตาม Priority: (1) ความยากทริปก่อนหน้า (2) ความไวกดขนของขึ้นเสร็จ (Orange→Green ทริปก่อน) (3) จำนวนดาว มาก→น้อย
- **Driver Rating (ดาว):** Admin/Super Admin ให้คะแนนคนขับ 0-5 ดาว เก็บเป็นตัวเลข ส่ง Frontend แสดงเป็น "รูปดาว" เท่านั้น (ห้ามโชว์ตัวเลข/คำอธิบาย)
- **Penalty (หักเงินหลายรายการ):** โมเดล `Penalty` ผูก User(คนขับ)+Trip เก็บรายการหักเงินหลายบรรทัด (จำนวน+เหตุผลบังคับ) — Supervisor/Admin เพิ่มได้
- **User Management:** Admin แก้ข้อมูลส่วนตัวพนักงานแต่ละคนได้
- **Monthly Trip History:** สรุปประวัติวิ่งงานรายเดือนของคนขับ — เฉพาะ Supervisor/Admin/Super Admin
- **Vehicle Assignment:** จัดการทะเบียนรถ + ผูกว่ารถคันไหนประจำคนขับคนไหน

**RBAC สรุปสิทธิ์:** ดูตาราง endpoint ใน skill.md ข้อ 6 — Backend ต้องใช้ `require_supervisor`/`require_admin` guard ทุก endpoint ชุดนี้ ห้ามหลุดให้ Driver เข้าถึง

## 6. Frontend Layout Refactor (ปรับโครงสร้างหน้าจอ — ห้าม Driver เข้าถึงเด็ดขาด)
โครงสร้างการแสดงผลใหม่ (ทุกหน้า/ตาราง/API ในข้อนี้จำกัดเฉพาะ Supervisor / Admin / Super Admin เท่านั้น):

- **6.1 Dashboard (สรุปภาพรวมอย่างเดียว):** เหลือเฉพาะการ์ดตัวเลขสถิติสรุป — รองาน / ขึ้นของ / ส่งของ / รอเช็กสลิป **ห้ามมีตารางคุมรถหรือรายละเอียดทริป และห้ามมีตารางสรุปหักเงินบน Dashboard อีกต่อไป**
- **6.2 Dispatch Page (หน้าจ่ายงาน):** ย้ายรายละเอียดเที่ยววิ่งของคนขับมาไว้ที่นี่ — คลิกชื่อคนขับใน Dispatch Queue เปิด Modal/Accordion แสดง Trip Details ของทริปที่กำลังวิ่ง · มี Search Bar ค้นหาแบบเรียลไทม์ด้วย "ชื่อคนขับ" หรือ "เลขทะเบียนรถ" (Backend: `GET /dispatch/queue?q=`)
- **6.3 Penalty Page (ระบบประวัติและสรุปการหักเงิน):** หน้า/แท็บแยกเฉพาะ — ฟิลเตอร์ตาม **เดือน/ปี (Month/Year Picker)** ดึงเฉพาะเดือน/ปีที่เลือก · ค้นหาด้วยชื่อคนขับ · คลิกชื่อคนขับเปิด Trip Details ของเที่ยวที่ถูกหักเงิน (Backend: `GET /penalties?driver_name=&month=&year=`)
- **6.4 Trip History Flow (ประวัติทริป):** บังคับลำดับขั้น — (1) เลือกคนขับ → (2) เลือกเดือน/ปี → (3) ระบบยิง API ดึงตารางประวัติทริปรายเดือนมาแสดง (Backend: `GET /users/{id}/history/monthly?year=&month=` คืนตารางทริปรายเที่ยว)
- **6.5 Trip Adjustment + Edit Reason (บันทึกเหตุผลการแก้ไขทริป):** Admin **และ** Supervisor แก้ข้อมูลทริป (ระยะทาง / ความยาก / เบี้ยเลี้ยง / หักเงิน) ได้ผ่าน `PATCH /trips/{id}/adjust` — **Request Body บังคับฟิลด์ `edit_reason` เสมอ** (schema-level) เพื่อบันทึกลง Audit Trail · Frontend ต้องเด้ง Alert Modal บังคับพิมพ์เหตุผลก่อนกดบันทึก

## 7. Manual Override, OCR Edit, Leaderboard & Audit Log (Driver เข้าถึงไม่ได้)
รอบฟีเจอร์เสริม 5 งาน — ทุก endpoint จำกัด Supervisor+/Admin+ ตามระบุ · action สำคัญลง Audit อัตโนมัติ

- **7.1 Manual Status Override (task 1):** `POST /trips/{id}/override-status` (Supervisor+) — เปลี่ยนสถานะทริป (WHITE/ORANGE/GREEN) แบบ manual · **บังคับ `reason`** · สำเร็จแล้วแจ้งเตือนคนขับ (stub push) + ลง Audit ("เปลี่ยนสถานะ (Manual Override)") · ทริป frozen เปลี่ยนไม่ได้ · Frontend เด้ง Modal ยืนยัน+เหตุผลก่อนยิง
- **7.2 Manual Edit OCR Amount (task 2):** `PATCH /receipts/{id}/amount` (Supervisor+) — **บังคับ `new_amount` + `reason`** · แก้ยอดได้ทั้งบิล draft/approved (ยังไม่ freeze) · ลง Audit ("แก้ยอดเงินใบเสร็จ (OCR)") · Frontend เด้ง Modal เตือน "แน่ใจหรือไม่?" + บังคับเหตุผล (ปุ่มยืนยัน disabled จนกรอก)
- **7.3 Deduction Leaderboard (task 3):** `GET /penalties/leaderboard?month=&year=` (Supervisor+) — group by คนขับ คืน `total_amount` + `count` เรียงจากมาก→น้อย · Frontend เป็นแท็บในหน้าประวัติหักเงิน (เลือกเดือน/ปี)
- **7.4 Fix "ยืนยันยอด" Button (task 4):** เปลี่ยนจาก `window.prompt` (กดไม่ติดในบาง browser/sandbox) → in-app Modal (`ReceiptAmountModal`) · อัปเดต UI ทันทีผ่าน react-query invalidate
- **7.5 Audit Log Page (task 5):** `GET /audit-logs?action=&target=&limit=` (**Admin+ เท่านั้น**) — อ่านจากตาราง `audit_logs` เดิม (มีอยู่แล้ว ไม่ต้อง migrate) · Frontend หน้าใหม่ `/admin-audit-log` แสดง ใคร/ทำอะไร/ที่ไหน/เมื่อไหร่/เหตุผล · เหตุการณ์จาก 7.1 และ 7.2 ถูก insert อัตโนมัติ