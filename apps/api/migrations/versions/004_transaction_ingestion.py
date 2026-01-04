"""Transaction ingestion fields - upload_id, source_hash, file_hash, ingestion_logs

Revision ID: 004_transaction_ingestion
Revises: 003_comprehensive_schema
Create Date: 2024-12-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '004_transaction_ingestion'
down_revision: Union[str, None] = '003_comprehensive_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add file_hash to data_uploads for file-level deduplication
    op.add_column('data_uploads', sa.Column('file_hash', sa.String(64), nullable=True))
    op.create_index('idx_data_uploads_file_hash', 'data_uploads', ['restaurant_id', 'file_hash'])

    # Add upload_id and source_hash to transactions for row-level deduplication
    op.add_column('transactions', sa.Column('upload_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('transactions', sa.Column('source_hash', sa.String(64), nullable=True))

    # Add foreign key constraint
    op.create_foreign_key(
        'fk_transactions_upload_id',
        'transactions', 'data_uploads',
        ['upload_id'], ['id'],
        ondelete='SET NULL'
    )

    # Add indices for performance
    op.create_index('idx_transactions_restaurant_date', 'transactions', ['restaurant_id', 'transaction_date'])
    op.create_index('idx_transactions_source_hash', 'transactions', ['restaurant_id', 'source_hash'])

    # Create ingestion_logs table for detailed error tracking
    op.create_table(
        'ingestion_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('upload_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('data_uploads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('row_number', sa.Integer(), nullable=False),
        sa.Column('field', sa.String(100), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('raw_value', sa.Text(), nullable=True),
        sa.Column('severity', sa.String(20), nullable=False, server_default='error'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now())
    )

    # Add index on upload_id for efficient error lookups
    op.create_index('idx_ingestion_logs_upload', 'ingestion_logs', ['upload_id'])


def downgrade() -> None:
    # Drop ingestion_logs table
    op.drop_index('idx_ingestion_logs_upload', table_name='ingestion_logs')
    op.drop_table('ingestion_logs')

    # Drop transaction indices
    op.drop_index('idx_transactions_source_hash', table_name='transactions')
    op.drop_index('idx_transactions_restaurant_date', table_name='transactions')

    # Drop transaction foreign key and columns
    op.drop_constraint('fk_transactions_upload_id', 'transactions', type_='foreignkey')
    op.drop_column('transactions', 'source_hash')
    op.drop_column('transactions', 'upload_id')

    # Drop data_uploads index and column
    op.drop_index('idx_data_uploads_file_hash', table_name='data_uploads')
    op.drop_column('data_uploads', 'file_hash')
