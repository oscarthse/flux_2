"""Add source_hash to transaction_items for row-level deduplication

Revision ID: 005_transaction_item_hash
Revises: 004_transaction_ingestion
Create Date: 2024-12-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '005_transaction_item_hash'
down_revision: Union[str, None] = '004_transaction_ingestion'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add source_hash to transaction_items for row-level deduplication
    op.add_column('transaction_items', sa.Column('source_hash', sa.String(64), nullable=True))

    # Add index for efficient duplicate checking
    op.create_index('idx_transaction_items_source_hash', 'transaction_items', ['source_hash'])


def downgrade() -> None:
    # Drop index and column
    op.drop_index('idx_transaction_items_source_hash', table_name='transaction_items')
    op.drop_column('transaction_items', 'source_hash')
