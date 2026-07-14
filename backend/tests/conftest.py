"""Pytest fixtures — ใช้ SQLite แยกไฟล์สำหรับเทสต์ (ตั้ง DATABASE_URL ก่อน import แอป)"""
import os

# ต้องตั้งก่อน import โมดูลแอป เพื่อให้ engine/SessionLocal ผูกกับ DB เทสต์
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app
from app.models import Role, User
from app.security import hash_password


@pytest.fixture()
def db_session():
    # สร้างตารางใหม่ทั้งหมดต่อ 1 test เพื่อความสะอาด แยกจากกัน
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    from app.database import SessionLocal

    db = SessionLocal()
    # seed ผู้ใช้ทดสอบ: driver, driver ที่ถูกระงับ, admin (รหัสผ่าน 1234)
    db.add_all([
        User(emp_id="D01", name="สมชาย ใจดี", phone="0810000001",
             role=Role.DRIVER, active=True, password_hash=hash_password("1234")),
        User(emp_id="D04", name="อนุชา ตรงเวลา", phone="0810000004",
             role=Role.DRIVER, active=False, password_hash=hash_password("1234")),
        User(emp_id="AD01", name="กมล ผู้จัดการ", phone="0830000001",
             role=Role.ADMIN, active=True, password_hash=hash_password("1234")),
    ])
    db.commit()
    yield db
    db.close()


@pytest.fixture()
def client(db_session):
    return TestClient(app)


def login(client, identifier, password="1234"):
    return client.post("/auth/login", json={"identifier": identifier, "password": password})


def pass_inspection(db, trip, driver):
    """ทางลัดสำหรับเทสต์: ส่งผลตรวจสภาพรถผ่านทุกข้อ (ด่านบังคับก่อน finish_loading)"""
    from app.services.inspection import submit_inspection

    return submit_inspection(db, trip, driver, {"tires": True, "lights": True, "tarp": True})
