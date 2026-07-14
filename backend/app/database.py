"""ตั้งค่า SQLAlchemy engine / session / declarative Base

รองรับทั้ง SQLite (dev) และ PostgreSQL (production) ผ่าน DATABASE_URL ใน config
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

# SQLite ต้องปิด check_same_thread เพื่อให้ FastAPI (หลาย thread) ใช้ connection เดียวกันได้
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency: เปิด session ต่อ 1 request แล้วปิดเสมอ"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
