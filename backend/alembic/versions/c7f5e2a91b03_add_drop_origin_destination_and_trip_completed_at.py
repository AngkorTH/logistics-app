"""add drop origin/destination + trip completed_at (Dynamic Multi-Drop)

Revision ID: c7f5e2a91b03
Revises: b4d81c6f2a97
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c7f5e2a91b03'
down_revision: Union[str, None] = 'b4d81c6f2a97'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # งานย่อย (Drop) ต้องมีต้นทาง/ปลายทางเสมอ — ข้อมูลเก่าถูก backfill จากชื่อจุดส่งเดิม
    op.add_column('drops', sa.Column('origin', sa.String(255), nullable=False, server_default=''))
    op.add_column('drops', sa.Column('destination', sa.String(255), nullable=False, server_default=''))
    op.execute("UPDATE drops SET destination = name WHERE destination = ''")
    op.execute("UPDATE drops SET origin = 'ไม่ระบุ (ข้อมูลเก่า)' WHERE origin = ''")

    # เที่ยวหลักจบสมบูรณ์เมื่อ Supervisor กด "จบเที่ยว" — คนละขั้นกับ closed_at/frozen
    op.add_column('trips', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))
    # ทริปเก่าที่ปิดงานไปแล้วถือว่าจบเที่ยวแล้ว (ย้อนหลังให้ตรงกับ flow ใหม่)
    op.execute("UPDATE trips SET completed_at = closed_at WHERE closed_at IS NOT NULL")


def downgrade() -> None:
    op.drop_column('trips', 'completed_at')
    op.drop_column('drops', 'destination')
    op.drop_column('drops', 'origin')
