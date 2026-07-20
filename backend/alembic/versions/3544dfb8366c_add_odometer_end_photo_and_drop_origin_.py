"""add odometer_end_photo + บังคับ drops.origin/destination ห้ามว่างระดับ DB

สรุปสิ่งที่เปลี่ยน:
1. trips.odometer_end_photo — URL รูปหน้าปัดไมล์ตอนจบงาน (บังคับถ่ายคู่กับเลขไมล์จบ)
2. drops.origin / drops.destination — ถอด server_default '' ออก (เดิมปล่อยให้ค่าว่าง
   ลอดเข้ามาได้เงียบๆ) แล้วเพิ่ม CheckConstraint ความยาวหลัง trim > 0

⚠️ ก่อนใส่ CheckConstraint ต้อง backfill แถวเก่าที่ origin/destination ว่างก่อน
ไม่งั้น ALTER ล้มทันที — เติมด้วย marker '(ไม่ระบุ)' ให้เห็นชัดว่าเป็นข้อมูลเก่าที่ขาด
ไม่ใช่ข้อมูลจริง (ห้ามเดาต้นทาง/ปลายทางแทนผู้ใช้)

Revision ID: 3544dfb8366c
Revises: d3b8a41c7e26
Create Date: 2026-07-19 21:40:50.544583
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3544dfb8366c'
down_revision: Union[str, None] = 'd3b8a41c7e26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BLANK = "(ไม่ระบุ)"   # marker สำหรับข้อมูลเก่าที่ไม่มีต้นทาง/ปลายทาง


def upgrade() -> None:
    # ---- 1) รูปหน้าปัดไมล์ตอนจบงาน ----
    with op.batch_alter_table("trips", schema=None) as batch_op:
        batch_op.add_column(sa.Column("odometer_end_photo", sa.String(length=255), nullable=True))

    # ---- 2) backfill แถวเก่าที่ค่าว่าง (ต้องทำก่อนใส่ CheckConstraint) ----
    op.execute(
        sa.text(
            "UPDATE drops SET origin = :v WHERE origin IS NULL OR trim(origin) = ''"
        ).bindparams(v=_BLANK)
    )
    op.execute(
        sa.text(
            "UPDATE drops SET destination = :v WHERE destination IS NULL OR trim(destination) = ''"
        ).bindparams(v=_BLANK)
    )

    # ---- 3) ถอด default '' + ใส่ CheckConstraint ----
    # batch mode = สร้างตารางใหม่แล้วย้ายข้อมูล (SQLite ALTER ไม่รองรับตรงๆ)
    with op.batch_alter_table("drops", schema=None) as batch_op:
        batch_op.alter_column(
            "origin",
            existing_type=sa.String(length=255),
            existing_nullable=False,
            server_default=None,
        )
        batch_op.alter_column(
            "destination",
            existing_type=sa.String(length=255),
            existing_nullable=False,
            server_default=None,
        )
        batch_op.create_check_constraint("ck_drop_origin_not_blank", "length(trim(origin)) > 0")
        batch_op.create_check_constraint(
            "ck_drop_destination_not_blank", "length(trim(destination)) > 0"
        )


def downgrade() -> None:
    with op.batch_alter_table("drops", schema=None) as batch_op:
        batch_op.drop_constraint("ck_drop_destination_not_blank", type_="check")
        batch_op.drop_constraint("ck_drop_origin_not_blank", type_="check")
        batch_op.alter_column(
            "destination",
            existing_type=sa.String(length=255),
            existing_nullable=False,
            server_default="",
        )
        batch_op.alter_column(
            "origin",
            existing_type=sa.String(length=255),
            existing_nullable=False,
            server_default="",
        )

    with op.batch_alter_table("trips", schema=None) as batch_op:
        batch_op.drop_column("odometer_end_photo")
