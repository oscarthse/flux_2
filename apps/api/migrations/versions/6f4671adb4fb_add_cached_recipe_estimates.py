"""add_cached_recipe_estimates

Revision ID: 6f4671adb4fb
Revises: 013_comprehensive_fixes
Create Date: 2026-01-02 20:35:24.650316

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6f4671adb4fb'
down_revision: Union[str, None] = '013_comprehensive_fixes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('cached_recipe_estimates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('menu_item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('menu_items.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('ingredients', postgresql.JSONB, nullable=False),
        sa.Column('total_estimated_cost', sa.Numeric(10, 2), nullable=False),
        sa.Column('confidence', sa.String(20), nullable=False),
        sa.Column('estimation_notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
    )

    op.create_index('idx_cached_recipe_estimates_menu_item', 'cached_recipe_estimates', ['menu_item_id'])


def downgrade() -> None:
    op.drop_index('idx_cached_recipe_estimates_menu_item')
    op.drop_table('cached_recipe_estimates')
