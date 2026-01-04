"""Add promotion tracking enhancements

Revision ID: 010_promotion_tracking_enhancements
Revises: 2d402a57df19_add_operating_hours_columns
Create Date: 2025-12-25

Adds:
- is_exploration flag to promotions (for unbiased elasticity learning)
- promotion_id FK to transaction_items (link sales to campaigns)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '010_promo_enhance'
down_revision: Union[str, None] = '214f256ebc5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_exploration flag to promotions
    # This enables 5% random exploration promos for unbiased elasticity learning
    op.add_column(
        'promotions',
        sa.Column('is_exploration', sa.Boolean(), nullable=False, server_default=sa.text('false'))
    )

    # Add promotion_id FK to transaction_items
    # Links each item sale to the promotion that drove it
    op.add_column(
        'transaction_items',
        sa.Column('promotion_id', UUID(as_uuid=True), nullable=True)
    )

    # Add foreign key constraint
    op.create_foreign_key(
        'fk_transaction_items_promotion',
        'transaction_items',
        'promotions',
        ['promotion_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Drop foreign key constraint
    op.drop_constraint('fk_transaction_items_promotion', 'transaction_items', type_='foreignkey')

    # Remove columns
    op.drop_column('transaction_items', 'promotion_id')
    op.drop_column('promotions', 'is_exploration')
