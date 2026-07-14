# Logistics ERP — Driver Management System

โปรเจกต์ระบบ ERP ติดตามงานขนส่ง/คนขับรถ (ภาษาไทยเป็นหลัก) แดชบอร์ดควบคุมทริป อัปโหลดหลักฐาน คำนวณเบี้ยเลี้ยง/หักเงิน และล็อกข้อมูลการเงินเมื่อปิดทริป

## ธุรกิจ / กติกา (สำคัญที่สุด)

กติกาธุรกิจทั้งหมด (state machine สถานะ White/Orange/Green, multi-drop 1–5 sub-trips, การอัปโหลดหลักฐาน, GPS geofence, OCR ใบเสร็จ, สูตรจ่ายเงิน, สิทธิ์ตาม role, audit log, การล็อกการเงิน/ขอปลดล็อก) อยู่ในสกิล **`logistics-erp-driver-rules`**

➡️ **ก่อนแก้หรือรีวิวโค้ดที่แตะ:** สถานะทริป, การอัปโหลดหลักฐาน, GPS, สูตรเงิน/การหักเงิน, สิทธิ์ผู้ใช้, audit log, หรือการปลดล็อกทริปที่ปิดแล้ว — ให้อ่านสกิลนี้ก่อนเสมอ กติกาพวกนี้เกี่ยวโยงกันและพลาดง่าย

## สแตกเทคโนโลยี

- **Prototype ปัจจุบัน:** SPA ไฟล์เดียว `prototype-ui.tsx.html` — React 18 + Babel standalone + Tailwind ผ่าน CDN (`<script type="text/babel-src">`), state จำลองด้วย `localStorage`/mock seed data ยังไม่มี backend จริง
- UI ภาษาไทย ฟอนต์ Noto Sans Thai / Segoe UI
- `FUEL_PRICE = 32` บาท/ลิตร (ค่าจำลอง)

## Roles (4 ระดับ)

`DRIVER` (พนักงานขับรถ) · `SUPERVISOR` (คนคุมงาน) · `ADMIN` (แอดมิน) · `SUPER_ADMIN` (ซุปเปอร์แอดมิน — อนุมัติคำขอปลดล็อกการเงินได้เท่านั้น)

## Routes

| Route | หน้า | เห็นได้โดย |
|---|---|---|
| `/dashboard` | แดชบอร์ด (สรุปสถานะ + งานรอดำเนินการ + audit log; คนขับเห็น "งานของฉัน" ที่นี่) | ทุก role |
| `/fleet-dispatch` | จัดรถ — สั่งงานรถ/ติดตามสถานะ/ตรวจบิล/คีย์เงิน-หักเงิน/ปิดงาน (ภาพรวมกองรถอยู่ที่นี่ ไม่อยู่ในแดชบอร์ด) | SUPERVISOR ขึ้นไป |
| `/financial-report` | รายงานการเงิน | SUPERVISOR ขึ้นไป |
| `/user-management` | จัดการพนักงาน | ADMIN ขึ้นไป |
| `/vehicle-inventory` | ทะเบียนรถ | SUPERVISOR ขึ้นไป |
| `/trip-history` | ประวัติทริป | ทุก role |
| `/correction-log` | คำขอแก้ไข/ปลดล็อก | SUPER_ADMIN เท่านั้น |
| `/profile-settings` | ตั้งค่าโปรไฟล์ | ทุก role |

## รันดูงาน

เป็นไฟล์ HTML เดียว เปิดผ่าน static server:

```bash
python -m http.server 8777 --bind 127.0.0.1
# แล้วเปิด http://127.0.0.1:8777/prototype-ui.tsx.html
```

## แนวทางการทำงาน

- คงภาษาไทยใน UI และคอมเมนต์ให้สอดคล้องกับโค้ดเดิม
- อย่า hard-block transition ที่กติกาบอกว่าให้ "เตือน" (เช่น ไปสถานะ Green ก่อนอัปโหลดผ้าใบ, ปิดทริปก่อนอัปรูปครบ) — ให้ยืนยันเตือน ไม่ใช่บล็อก
- ตัวเลขการเงินของทริปที่ปิดแล้ว **ล็อกถาวร** ห้ามแก้ผ่าน edit endpoint ปกติ ต้องผ่าน flow ขอปลดล็อก + log ค่าเก่า/ใหม่เท่านั้น
