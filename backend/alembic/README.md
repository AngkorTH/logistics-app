# Alembic migrations

- สร้าง migration ใหม่จาก models: `alembic revision --autogenerate -m "message"`
- อัปเดต DB ให้เป็นเวอร์ชันล่าสุด: `alembic upgrade head`
- ย้อนกลับ 1 ขั้น: `alembic downgrade -1`

URL ของ DB ดึงจาก `.env` (`DATABASE_URL`) โดยอัตโนมัติผ่าน `env.py`
