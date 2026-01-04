"""
Migration 012: Recipe Intelligence Schema

Adds Epic 3 models for recipe matching, COGS calculation, and procurement.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '012_recipe_intel'
down_revision = '011_operating_hours'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to ingredients table
    op.add_column('ingredients', sa.Column('waste_factor', sa.Numeric(3, 2), server_default='0.0'))
    op.add_column('ingredients', sa.Column('allergens', postgresql.JSONB, server_default='[]'))
    op.add_column('ingredients', sa.Column('perishability_days', sa.Integer))

    # Create standard_recipes table
    op.create_table(
        'standard_recipes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('cuisine_type', sa.String(100)),
        sa.Column('category', sa.String(100)),
        sa.Column('servings', sa.Integer, server_default='1'),
        sa.Column('prep_time_minutes', sa.Integer),
        sa.Column('skill_level', sa.Integer),
        sa.Column('description', sa.Text),
        sa.Column('dietary_tags', postgresql.JSONB, server_default='[]'),
        sa.Column('embedding', postgresql.JSONB),
        sa.Column('is_system', sa.Boolean, server_default='true'),
        sa.Column('source', sa.String(100)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('idx_standard_recipes_name', 'standard_recipes', ['name'])
    op.create_index('idx_standard_recipes_cuisine', 'standard_recipes', ['cuisine_type'])

    # Create standard_recipe_ingredients table
    op.create_table(
        'standard_recipe_ingredients',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('standard_recipe_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('standard_recipes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ingredient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ingredients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('quantity', sa.Numeric(10, 4), nullable=False),
        sa.Column('unit', sa.String(50), nullable=False),
        sa.Column('preparation', sa.String(100)),
        sa.Column('is_optional', sa.Boolean, server_default='false'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Create menu_item_recipes table
    op.create_table(
        'menu_item_recipes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('menu_item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('menu_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('standard_recipe_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('standard_recipes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('yield_multiplier', sa.Numeric(4, 2), server_default='1.0'),
        sa.Column('confirmed_by_user', sa.Boolean, server_default='false'),
        sa.Column('confidence_score', sa.Numeric(3, 2)),
        sa.Column('matched_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('confirmed_at', sa.DateTime),
    )
    op.create_index('idx_menu_item_recipes_menu_item', 'menu_item_recipes', ['menu_item_id'])
    op.create_index('idx_menu_item_recipes_confirmed', 'menu_item_recipes', ['confirmed_by_user'])

    # Create ingredient_cost_history table
    op.create_table(
        'ingredient_cost_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('ingredient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ingredients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('restaurants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('cost_per_unit', sa.Numeric(10, 4), nullable=False),
        sa.Column('effective_date', sa.Date, nullable=False),
        sa.Column('source', sa.String(50)),
        sa.Column('notes', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('idx_cost_history_ingredient_date', 'ingredient_cost_history', ['ingredient_id', 'effective_date'])


def downgrade() -> None:
    op.drop_table('ingredient_cost_history')
    op.drop_table('menu_item_recipes')
    op.drop_table('standard_recipe_ingredients')
    op.drop_table('standard_recipes')

    op.drop_column('ingredients', 'perishability_days')
    op.drop_column('ingredients', 'allergens')
    op.drop_column('ingredients', 'waste_factor')
