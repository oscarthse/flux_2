"""create_data_health_scores_table

Revision ID: 007_data_health_scores
Revises: 006_menu_item_extraction
Create Date: 2025-12-23 18:20:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '007_data_health_scores'
down_revision = '006_menu_item_extraction'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table('data_health_scores',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('overall_score', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('completeness_score', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('consistency_score', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('timeliness_score', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('accuracy_score', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('component_breakdown', sa.JSON(), nullable=False),
        sa.Column('recommendations', sa.JSON(), nullable=False),
        sa.Column('calculated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Index for fast retrieval of latest score per restaurant
    op.create_index('idx_health_scores_restaurant_date', 'data_health_scores',
                    ['restaurant_id', 'calculated_at'])

def downgrade() -> None:
    op.drop_index('idx_health_scores_restaurant_date', table_name='data_health_scores')
    op.drop_table('data_health_scores')
