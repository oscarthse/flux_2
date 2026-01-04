"""Comprehensive schema v2 - Menu, Inventory, Labor, Forecasts, Promotions

Revision ID: 003_comprehensive_schema
Revises: 002_transactions
Create Date: 2024-12-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '003_comprehensive_schema'
down_revision: Union[str, None] = '002_transactions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ========================================
    # MENU & INGREDIENTS
    # ========================================

    # Menu categories
    op.create_table(
        'menu_categories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('restaurants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('display_order', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('restaurant_id', 'name', name='uq_menu_categories_restaurant_name')
    )

    # Menu items
    op.create_table(
        'menu_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('restaurants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('menu_categories.id', ondelete='SET NULL')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('price', sa.Numeric(10, 2), nullable=False),
        sa.Column('cost_override', sa.Numeric(10, 2)),
        sa.Column('prep_time_minutes', sa.Integer()),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now())
    )
    op.create_index('idx_menu_items_restaurant', 'menu_items', ['restaurant_id'])
    op.create_index('idx_menu_items_active', 'menu_items', ['restaurant_id', 'is_active'])

    # Ingredient categories
    op.create_table(
        'ingredient_categories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('restaurants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('restaurant_id', 'name', name='uq_ingredient_categories_restaurant_name')
    )

    # Ingredients
    op.create_table(
        'ingredients',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('restaurants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ingredient_categories.id', ondelete='SET NULL')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('unit', sa.String(50), nullable=False),
        sa.Column('unit_cost', sa.Numeric(10, 4)),
        sa.Column('shelf_life_days', sa.Integer()),
        sa.Column('min_stock_level', sa.Numeric(10, 3)),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now())
    )
    op.create_index('idx_ingredients_restaurant', 'ingredients', ['restaurant_id'])

    # Recipes
    op.create_table(
        'recipes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('menu_item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('menu_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ingredient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ingredients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('quantity', sa.Numeric(10, 4), nullable=False),
        sa.Column('unit', sa.String(50), nullable=False),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('menu_item_id', 'ingredient_id', name='uq_recipes_item_ingredient')
    )
    op.create_index('idx_recipes_menu_item', 'recipes', ['menu_item_id'])
    op.create_index('idx_recipes_ingredient', 'recipes', ['ingredient_id'])

    # ========================================
    # INVENTORY
    # ========================================

    op.create_table(
        'inventory',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('restaurants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ingredient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ingredients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('quantity', sa.Numeric(10, 3), nullable=False),
        sa.Column('unit', sa.String(50), nullable=False),
        sa.Column('batch_id', sa.String(100)),
        sa.Column('expiry_date', sa.Date()),
        sa.Column('received_date', sa.Date(), server_default=sa.text('CURRENT_DATE')),
        sa.Column('unit_cost', sa.Numeric(10, 4)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now())
    )
    op.create_index('idx_inventory_restaurant', 'inventory', ['restaurant_id'])
    op.create_index('idx_inventory_ingredient', 'inventory', ['ingredient_id'])
    op.create_index('idx_inventory_expiry', 'inventory', ['expiry_date'])

    op.create_table(
        'inventory_movements',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('inventory_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inventory.id', ondelete='SET NULL')),
        sa.Column('ingredient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ingredients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('restaurants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('movement_type', sa.String(50), nullable=False),
        sa.Column('quantity', sa.Numeric(10, 3), nullable=False),
        sa.Column('unit', sa.String(50), nullable=False),
        sa.Column('reference_id', postgresql.UUID(as_uuid=True)),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now())
    )
    op.create_index('idx_inventory_movements_restaurant', 'inventory_movements', ['restaurant_id'])
    op.create_index('idx_inventory_movements_date', 'inventory_movements', ['created_at'])

    # ========================================
    # LABOR & SCHEDULING
    # ========================================

    op.create_table(
        'employee_roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('restaurants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('hourly_rate_default', sa.Numeric(10, 2)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('restaurant_id', 'name', name='uq_employee_roles_restaurant_name')
    )

    op.create_table(
        'employees',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('restaurants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255)),
        sa.Column('phone', sa.String(50)),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('employee_roles.id', ondelete='SET NULL')),
        sa.Column('hourly_rate', sa.Numeric(10, 2), nullable=False),
        sa.Column('min_hours_per_week', sa.Numeric(5, 2), default=0),
        sa.Column('max_hours_per_week', sa.Numeric(5, 2), default=40),
        sa.Column('hire_date', sa.Date()),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now())
    )
    op.create_index('idx_employees_restaurant', 'employees', ['restaurant_id'])
    op.create_index('idx_employees_active', 'employees', ['restaurant_id', 'is_active'])

    op.create_table(
        'skills',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('restaurants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('restaurant_id', 'name', name='uq_skills_restaurant_name')
    )

    op.create_table(
        'employee_skills',
        sa.Column('employee_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False),
        sa.Column('skill_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('skills.id', ondelete='CASCADE'), nullable=False),
        sa.Column('certified_date', sa.Date()),
        sa.Column('expiry_date', sa.Date()),
        sa.PrimaryKeyConstraint('employee_id', 'skill_id')
    )

    op.create_table(
        'shift_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('restaurants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('required_staff', sa.Integer(), default=1),
        sa.Column('required_skill_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('skills.id', ondelete='SET NULL')),
        sa.Column('days_of_week', postgresql.ARRAY(sa.Integer())),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now())
    )

    op.create_table(
        'employee_availability',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('employee_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False),
        sa.Column('day_of_week', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.Time()),
        sa.Column('end_time', sa.Time()),
        sa.Column('is_available', sa.Boolean(), default=True),
        sa.Column('preference', sa.Integer(), default=0),
        sa.Column('effective_from', sa.Date(), server_default=sa.text('CURRENT_DATE')),
        sa.Column('effective_to', sa.Date()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now())
    )
    op.create_index('idx_availability_employee', 'employee_availability', ['employee_id'])

    op.create_table(
        'scheduled_shifts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('restaurants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('employee_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False),
        sa.Column('shift_date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('employee_roles.id', ondelete='SET NULL')),
        sa.Column('status', sa.String(20), default='scheduled'),
        sa.Column('actual_start_time', sa.Time()),
        sa.Column('actual_end_time', sa.Time()),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now())
    )
    op.create_index('idx_scheduled_shifts_restaurant', 'scheduled_shifts', ['restaurant_id'])
    op.create_index('idx_scheduled_shifts_employee', 'scheduled_shifts', ['employee_id'])
    op.create_index('idx_scheduled_shifts_date', 'scheduled_shifts', ['shift_date'])

    # ========================================
    # FORECASTING & ANALYTICS
    # ========================================

    op.create_table(
        'demand_forecasts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('restaurants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('menu_item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('menu_items.id', ondelete='CASCADE')),
        sa.Column('forecast_date', sa.Date(), nullable=False),
        sa.Column('predicted_quantity', sa.Numeric(10, 2), nullable=False),
        sa.Column('lower_bound', sa.Numeric(10, 2)),
        sa.Column('upper_bound', sa.Numeric(10, 2)),
        sa.Column('model_version', sa.String(50)),
        sa.Column('factors', postgresql.JSONB()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now())
    )
    op.create_index('idx_forecasts_restaurant', 'demand_forecasts', ['restaurant_id'])
    op.create_index('idx_forecasts_date', 'demand_forecasts', ['forecast_date'])

    op.create_table(
        'staffing_forecasts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('restaurants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('forecast_date', sa.Date(), nullable=False),
        sa.Column('hour_of_day', sa.Integer(), nullable=False),
        sa.Column('predicted_covers', sa.Integer()),
        sa.Column('recommended_staff', sa.Integer()),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('employee_roles.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now())
    )
    op.create_index('idx_staffing_forecasts_date', 'staffing_forecasts', ['restaurant_id', 'forecast_date'])

    # ========================================
    # PROMOTIONS
    # ========================================

    op.create_table(
        'promotions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('restaurants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('menu_item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('menu_items.id', ondelete='CASCADE')),
        sa.Column('name', sa.String(255)),
        sa.Column('discount_type', sa.String(20), nullable=False),
        sa.Column('discount_value', sa.Numeric(10, 2), nullable=False),
        sa.Column('min_margin', sa.Numeric(5, 2)),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(20), default='draft'),
        sa.Column('trigger_reason', sa.String(100)),
        sa.Column('expected_lift', sa.Numeric(5, 2)),
        sa.Column('actual_lift', sa.Numeric(5, 2)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now())
    )
    op.create_index('idx_promotions_restaurant', 'promotions', ['restaurant_id'])
    op.create_index('idx_promotions_dates', 'promotions', ['start_date', 'end_date'])

    op.create_table(
        'price_elasticity',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('restaurants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('menu_item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('menu_items.id', ondelete='CASCADE')),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('menu_categories.id', ondelete='CASCADE')),
        sa.Column('elasticity', sa.Numeric(5, 3), nullable=False),
        sa.Column('confidence', sa.Numeric(5, 3)),
        sa.Column('sample_size', sa.Integer()),
        sa.Column('last_updated', sa.DateTime(), server_default=sa.func.now())
    )

    # ========================================
    # EXTERNAL DATA
    # ========================================

    op.create_table(
        'weather_data',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('location', sa.String(100), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('temp_high', sa.Numeric(5, 2)),
        sa.Column('temp_low', sa.Numeric(5, 2)),
        sa.Column('precipitation_mm', sa.Numeric(5, 2)),
        sa.Column('conditions', sa.String(50)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('location', 'date', name='uq_weather_location_date')
    )

    op.create_table(
        'local_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('restaurants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('event_date', sa.Date(), nullable=False),
        sa.Column('event_type', sa.String(50)),
        sa.Column('expected_impact', sa.Numeric(5, 2)),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now())
    )
    op.create_index('idx_events_restaurant', 'local_events', ['restaurant_id'])
    op.create_index('idx_events_date', 'local_events', ['event_date'])

    # ========================================
    # SETTINGS & AUDIT
    # ========================================

    op.create_table(
        'restaurant_settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('restaurants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('setting_key', sa.String(100), nullable=False),
        sa.Column('setting_value', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('restaurant_id', 'setting_key', name='uq_settings_restaurant_key')
    )

    op.create_table(
        'algorithm_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('restaurants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('algorithm_name', sa.String(100), nullable=False),
        sa.Column('run_started_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('run_completed_at', sa.DateTime()),
        sa.Column('status', sa.String(20), default='running'),
        sa.Column('input_params', postgresql.JSONB()),
        sa.Column('output_summary', postgresql.JSONB()),
        sa.Column('error_message', sa.Text())
    )
    op.create_index('idx_algorithm_runs_restaurant', 'algorithm_runs', ['restaurant_id'])
    op.create_index('idx_algorithm_runs_date', 'algorithm_runs', ['run_started_at'])


def downgrade() -> None:
    op.drop_table('algorithm_runs')
    op.drop_table('restaurant_settings')
    op.drop_table('local_events')
    op.drop_table('weather_data')
    op.drop_table('price_elasticity')
    op.drop_table('promotions')
    op.drop_table('staffing_forecasts')
    op.drop_table('demand_forecasts')
    op.drop_table('scheduled_shifts')
    op.drop_table('employee_availability')
    op.drop_table('shift_templates')
    op.drop_table('employee_skills')
    op.drop_table('skills')
    op.drop_table('employees')
    op.drop_table('employee_roles')
    op.drop_table('inventory_movements')
    op.drop_table('inventory')
    op.drop_table('recipes')
    op.drop_table('ingredients')
    op.drop_table('ingredient_categories')
    op.drop_table('menu_items')
    op.drop_table('menu_categories')
