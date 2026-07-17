"""add vehicle status and maintenance_reports

Revision ID: 7c3a1e9d0af2
Revises: 21e2370960e8
Create Date: 2026-07-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c3a1e9d0af2'
down_revision: Union[str, None] = '21e2370960e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # สถานะรถ — รถที่คนขับแจ้งเหตุจะถูกตั้งเป็น MAINTENANCE (ล็อกจ่ายงาน)
    with op.batch_alter_table('vehicles', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'status',
                sa.Enum('AVAILABLE', 'MAINTENANCE', name='vehiclestatus'),
                nullable=False,
                server_default='AVAILABLE',
            )
        )
        batch_op.create_index(batch_op.f('ix_vehicles_status'), ['status'], unique=False)

    # ตารางบันทึกประวัติการแจ้งเหตุ/ซ่อมบำรุงจากคนขับ
    op.create_table(
        'maintenance_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('driver_id', sa.Integer(), nullable=False),
        sa.Column('vehicle_id', sa.Integer(), nullable=True),
        sa.Column('plate', sa.String(length=50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('photo', sa.String(length=255), nullable=True),
        sa.Column('status', sa.Enum('OPEN', 'RESOLVED', name='incidentstatus'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_by', sa.Integer(), nullable=True),
        sa.Column('resolver_name', sa.String(length=120), nullable=False),
        sa.Column('resolver_note', sa.Text(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['driver_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('maintenance_reports', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_maintenance_reports_code'), ['code'], unique=True)
        batch_op.create_index(batch_op.f('ix_maintenance_reports_driver_id'), ['driver_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_maintenance_reports_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_maintenance_reports_vehicle_id'), ['vehicle_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('maintenance_reports', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_maintenance_reports_vehicle_id'))
        batch_op.drop_index(batch_op.f('ix_maintenance_reports_status'))
        batch_op.drop_index(batch_op.f('ix_maintenance_reports_driver_id'))
        batch_op.drop_index(batch_op.f('ix_maintenance_reports_code'))
    op.drop_table('maintenance_reports')

    with op.batch_alter_table('vehicles', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_vehicles_status'))
        batch_op.drop_column('status')
