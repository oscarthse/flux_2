"""Add operating hours tables

Revision ID: 011_operating_hours
Revises: 010_promo_enhance
Create Date: 2025-12-25

Adds:
- operating_hours table for regular weekly schedule
- service_periods table for exceptions (holidays, closures)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '011_operating_hours'
down_revision: Union[str, None] = '010_promo_enhance'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create operating_hours table
    op.create_table(
        'operating_hours',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('restaurant_id', UUID(as_uuid=True), sa.ForeignKey('restaurants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('day_of_week', sa.Integer(), nullable=False),
        sa.Column('open_time', sa.Time(), nullable=True),
        sa.Column('close_time', sa.Time(), nullable=True),
        sa.Column('is_closed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Unique constraint: one entry per restaurant-day
    op.create_index(
        'idx_operating_hours_restaurant_day',
        'operating_hours',
        ['restaurant_id', 'day_of_week'],
        unique=True
    )

    # Create service_periods table
    op.create_table(
        'service_periods',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('restaurant_id', UUID(as_uuid=True), sa.ForeignKey('restaurants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('open_time', sa.Time(), nullable=True),
        sa.Column('close_time', sa.Time(), nullable=True),
        sa.Column('is_closed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('reason', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Unique constraint: one entry per restaurant-date
    op.create_index(
        'idx_service_periods_restaurant_date',
        'service_periods',
        ['restaurant_id', 'date'],
        unique=True
    )


def downgrade() -> None:
    op.drop_index('idx_service_periods_restaurant_date', table_name='service_periods')
    op.drop_table('service_periods')
    op.drop_index('idx_operating_hours_restaurant_day', table_name='operating_hours')
    op.drop_table('operating_hours')
