"""add_confirmed_flag_to_cache

Revision ID: 558c88a5498e
Revises: 6f4671adb4fb
Create Date: 2026-01-02 20:45:02.575689

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '558c88a5498e'
down_revision: Union[str, None] = '6f4671adb4fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('cached_recipe_estimates',
        sa.Column('is_confirmed', sa.Boolean, server_default='false', nullable=False)
    )
    op.add_column('cached_recipe_estimates',
        sa.Column('confirmed_at', sa.DateTime, nullable=True)
    )


def downgrade() -> None:
    op.drop_column('cached_recipe_estimates', 'confirmed_at')
    op.drop_column('cached_recipe_estimates', 'is_confirmed')
