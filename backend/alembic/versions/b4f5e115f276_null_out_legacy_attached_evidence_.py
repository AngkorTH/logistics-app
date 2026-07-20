"""ล้าง marker "attached" ในช่องรูปหลักฐาน → NULL

ก่อนมีระบบไฟล์ (Phase 4) ระบบเก็บแค่ธงว่า "แนบแล้ว" เป็นสตริง "attached"
ตอนนี้ทุกช่องรูปเก็บ URL ไฟล์จริง (/uploads/...) เท่านั้น marker เก่าจึงเป็นข้อมูลลวง:
มันบอกว่ามีหลักฐาน แต่เปิดดูไม่ได้ ไม่มีไฟล์อยู่จริง

NULL = "ไม่มีหลักฐาน" ซึ่งเป็นความจริงของแถวพวกนี้
⚠️ ไม่แปลงเป็น path ปลอม เพราะจะเป็นการสร้างหลักฐานที่ไม่มีอยู่จริง

ขอบเขต: สแกนแล้วพบ marker เฉพาะ drops.photo / drops.tarp เท่านั้น
(receipts.photo · trips.odometer_*_photo · inspections.defect_photo ·
incidents.photo · maintenance_reports.photo สะอาดอยู่แล้ว — เป็น /uploads/... ทั้งหมด)
แต่กวาดทุกตารางไว้เลยเผื่อ DB เครื่องอื่นมีตกค้าง

Revision ID: b4f5e115f276
Revises: 3544dfb8366c
Create Date: 2026-07-19 21:54:21.028700
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4f5e115f276'
down_revision: Union[str, None] = '3544dfb8366c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (ตาราง, คอลัมน์รูป) ทุกช่องหลักฐานในระบบ
_PHOTO_COLUMNS = [
    ("drops", "photo"),
    ("drops", "tarp"),
    ("receipts", "photo"),
    ("trips", "odometer_start_photo"),
    ("trips", "odometer_end_photo"),
    ("inspections", "defect_photo"),
    ("incidents", "photo"),
    ("maintenance_reports", "photo"),
]

# ค่าที่ถือว่า "ไม่ใช่ไฟล์รูปจริง" — ธงยุคเก่าและค่าว่างทุกแบบ
_JUNK = ("attached", "true", "True", "1", "")


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = set(inspector.get_table_names())

    for table, column in _PHOTO_COLUMNS:
        if table not in existing:
            continue  # ตารางยังไม่ถูกสร้างใน DB นี้ — ข้าม
        if column not in {c["name"] for c in inspector.get_columns(table)}:
            continue
        conn.execute(
            sa.text(
                f"UPDATE {table} SET {column} = NULL "
                f"WHERE {column} IS NOT NULL AND trim({column}) IN :junk"
            ).bindparams(sa.bindparam("junk", value=_JUNK, expanding=True))
        )


def downgrade() -> None:
    """ย้อนกลับไม่ได้ — โดยตั้งใจ

    marker "attached" ไม่มีข้อมูลอะไรให้กู้ (ไม่รู้ว่าแถวไหนเคยเป็น marker
    แถวไหนไม่เคยมีรูปมาแต่ต้น) การเดาใส่กลับจะสร้างหลักฐานปลอมให้แถวที่ไม่ควรมี
    ถ้าต้องย้อนจริง ให้กู้จากไฟล์ backup ของฐานข้อมูลแทน
    """
    pass
