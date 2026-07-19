"""add fuel liters and km_per_liter

Revision ID: 9a2c4b71d5e3
Revises: 7c3a1e9d0af2
Create Date: 2026-07-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a2c4b71d5e3'
down_revision: Union[str, None] = '7c3a1e9d0af2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # เลขไมล์ + อัตราสิ้นเปลืองระดับทริป
    with op.batch_alter_table('trips', schema=None) as batch_op:
        batch_op.add_column(sa.Column('odometer_start', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('odometer_end', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('km_per_liter', sa.Float(), nullable=True))

    # บิล: จำนวนลิตร + ผูกทริปตรงๆ ได้ (บิลเติมน้ำมันระหว่างทาง ไม่ผูกจุดส่ง)
    with op.batch_alter_table('receipts', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('liters', sa.Float(), nullable=False, server_default='0')
        )
        batch_op.add_column(sa.Column('trip_id', sa.Integer(), nullable=True))
        batch_op.alter_column('drop_id', existing_type=sa.Integer(), nullable=True)
        batch_op.create_index(batch_op.f('ix_receipts_trip_id'), ['trip_id'], unique=False)
        batch_op.create_foreign_key('fk_receipts_trip_id', 'trips', ['trip_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('receipts', schema=None) as batch_op:
        batch_op.drop_constraint('fk_receipts_trip_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_receipts_trip_id'))
        batch_op.alter_column('drop_id', existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column('trip_id')
        batch_op.drop_column('liters')

    with op.batch_alter_table('trips', schema=None) as batch_op:
        batch_op.drop_column('km_per_liter')
        batch_op.drop_column('odometer_end')
        batch_op.drop_column('odometer_start')
