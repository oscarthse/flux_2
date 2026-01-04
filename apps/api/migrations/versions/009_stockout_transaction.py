"""Add stockout_occurred to transactions

Revision ID: 009_stockout_transaction
Revises: 008_stockout_tracking
Create Date: 2025-12-23

"""
from alembic import op
import sqlalchemy as sa


revision = '009_stockout_transaction'
down_revision = '008_stockout_tracking'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('transactions', sa.Column('stockout_occurred', sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column('transactions', 'stockout_occurred')
