"""add drop revenue + per-leg difficulty (เบี้ยเลี้ยง = รายได้ต่อขา × %ความยาก)

Revision ID: d3b8a41c7e26
Revises: c7f5e2a91b03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd3b8a41c7e26'
down_revision: Union[str, None] = 'c7f5e2a91b03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('drops', sa.Column('revenue', sa.Float(), nullable=False, server_default='0'))
    op.add_column(
        'drops',
        sa.Column(
            'difficulty',
            sa.Enum('EASY', 'MEDIUM', 'HARD', name='tripdifficulty'),
            nullable=False,
            server_default='MEDIUM',
        ),
    )
    # ข้อมูลเก่า: ยึดความยากจากทริปแม่ แล้วถอดรายได้กลับจากเบี้ยเลี้ยงที่บันทึกไว้
    # (revenue = allowance ÷ เปอร์เซ็นต์ความยาก) เพื่อให้ยอดเบี้ยเลี้ยงเดิมไม่เปลี่ยน
    op.execute("""
        UPDATE drops SET difficulty = (
            SELECT trips.difficulty FROM trips WHERE trips.id = drops.trip_id
        ) WHERE trip_id IS NOT NULL
    """)
    op.execute("""
        UPDATE drops SET revenue = ROUND(allowance / CASE difficulty
            WHEN 'EASY' THEN 0.05 WHEN 'HARD' THEN 0.10 ELSE 0.07 END, 2)
        WHERE allowance > 0
    """)


def downgrade() -> None:
    op.drop_column('drops', 'difficulty')
    op.drop_column('drops', 'revenue')
