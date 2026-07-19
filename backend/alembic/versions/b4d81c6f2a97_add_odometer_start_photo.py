"""add odometer_start_photo

Revision ID: b4d81c6f2a97
Revises: 9a2c4b71d5e3
Create Date: 2026-07-19 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4d81c6f2a97'
down_revision: Union[str, None] = '9a2c4b71d5e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # รูปหน้าปัดไมล์ตอนเริ่มงาน (บังคับถ่ายคู่กับเลขไมล์เริ่ม)
    with op.batch_alter_table('trips', schema=None) as batch_op:
        batch_op.add_column(sa.Column('odometer_start_photo', sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('trips', schema=None) as batch_op:
        batch_op.drop_column('odometer_start_photo')
