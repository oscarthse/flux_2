"""Add inventory_snapshots table for stockout tracking

Revision ID: 008_stockout_tracking
Revises: 007_data_health_scores
Create Date: 2025-12-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '008_stockout_tracking'
down_revision = '007_data_health_scores'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create inventory_snapshots table
    op.create_table('inventory_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('menu_item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('available_qty', sa.Numeric(precision=10, scale=0), nullable=True),
        sa.Column('stockout_flag', sa.String(1), nullable=False, server_default='N'),
        sa.Column('source', sa.String(50), nullable=False, server_default='manual'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['menu_item_id'], ['menu_items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Unique constraint: one snapshot per item per day per restaurant
    op.create_index('idx_inventory_unique', 'inventory_snapshots',
                    ['restaurant_id', 'menu_item_id', 'date'], unique=True)

    # Fast lookup by restaurant and date range
    op.create_index('idx_inventory_restaurant_date', 'inventory_snapshots',
                    ['restaurant_id', 'date'])


def downgrade() -> None:
    op.drop_index('idx_inventory_restaurant_date', table_name='inventory_snapshots')
    op.drop_index('idx_inventory_unique', table_name='inventory_snapshots')
    op.drop_table('inventory_snapshots')
