"""โหลดค่า config จาก environment (.env) ด้วย pydantic-settings"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ค่าเริ่มต้นชี้ไป SQLite เพื่อให้รันทดสอบได้ทันทีโดยไม่ต้องตั้ง PostgreSQL
    DATABASE_URL: str = "sqlite:///./logistics.db"

    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720

    DEBUG: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
