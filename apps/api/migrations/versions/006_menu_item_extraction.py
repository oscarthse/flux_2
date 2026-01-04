"""Menu item extraction fields - category_path, first/last_seen, auto_created, confidence, price_history

Revision ID: 006_menu_item_extraction
Revises: 005_transaction_item_hash
Create Date: 2024-12-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '006_menu_item_extraction'
down_revision: Union[str, None] = '005_transaction_item_hash'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new fields to menu_items for auto-creation and categorization
    op.add_column('menu_items', sa.Column('category_path', sa.String(255), nullable=True))
    op.add_column('menu_items', sa.Column('first_seen', sa.DateTime(), nullable=True))
    op.add_column('menu_items', sa.Column('last_seen', sa.DateTime(), nullable=True))
    op.add_column('menu_items', sa.Column('auto_created', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('menu_items', sa.Column('confidence_score', sa.Numeric(3, 2), nullable=True))

    # Create menu_item_price_history table
    op.create_table(
        'menu_item_price_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('menu_item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('menu_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('price', sa.Numeric(10, 2), nullable=False),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now())
    )

    # Add indices for efficient queries
    op.create_index('idx_menu_items_auto_created', 'menu_items', ['restaurant_id', 'auto_created'])
    op.create_index('idx_menu_items_confidence', 'menu_items', ['restaurant_id', 'confidence_score'])
    op.create_index('idx_price_history_item_date', 'menu_item_price_history', ['menu_item_id', 'effective_date'])


def downgrade() -> None:
    # Drop indices
    op.drop_index('idx_price_history_item_date', table_name='menu_item_price_history')
    op.drop_index('idx_menu_items_confidence', table_name='menu_items')
    op.drop_index('idx_menu_items_auto_created', table_name='menu_items')

    # Drop price history table
    op.drop_table('menu_item_price_history')

    # Drop menu_items columns
    op.drop_column('menu_items', 'confidence_score')
    op.drop_column('menu_items', 'auto_created')
    op.drop_column('menu_items', 'last_seen')
    op.drop_column('menu_items', 'first_seen')
    op.drop_column('menu_items', 'category_path')
