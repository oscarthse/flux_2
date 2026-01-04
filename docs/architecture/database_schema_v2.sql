-- Flux Database Schema v2.0
-- Comprehensive schema supporting all algorithms
-- Designed for flexibility and future extensibility

-- ============================================
-- CORE ENTITIES
-- ============================================

-- Users (already exists, keeping for reference)
-- restaurants (already exists, keeping for reference)
-- data_uploads (already exists, keeping for reference)

-- ============================================
-- MENU & INGREDIENTS
-- ============================================

-- Categories for menu items (appetizers, mains, desserts, drinks)
CREATE TABLE menu_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(restaurant_id, name)
);

-- Menu items
CREATE TABLE menu_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    category_id UUID REFERENCES menu_categories(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    cost_override DECIMAL(10,2),  -- Manual cost if no recipe
    prep_time_minutes INTEGER,     -- For labor allocation
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_menu_items_restaurant ON menu_items(restaurant_id);
CREATE INDEX idx_menu_items_active ON menu_items(restaurant_id, is_active);

-- Ingredient categories (produce, dairy, meat, dry goods, etc.)
CREATE TABLE ingredient_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(restaurant_id, name)
);

-- Ingredients master list
CREATE TABLE ingredients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    category_id UUID REFERENCES ingredient_categories(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    unit VARCHAR(50) NOT NULL,  -- kg, liters, units, etc.
    unit_cost DECIMAL(10,4),     -- Cost per unit
    supplier_id UUID,            -- Future: link to suppliers table
    shelf_life_days INTEGER,     -- Default shelf life
    min_stock_level DECIMAL(10,3),  -- Reorder point
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_ingredients_restaurant ON ingredients(restaurant_id);

-- Recipes: link menu items to ingredients
CREATE TABLE recipes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    menu_item_id UUID NOT NULL REFERENCES menu_items(id) ON DELETE CASCADE,
    ingredient_id UUID NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    quantity DECIMAL(10,4) NOT NULL,  -- Amount of ingredient per dish
    unit VARCHAR(50) NOT NULL,         -- Unit for this recipe line
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(menu_item_id, ingredient_id)
);
CREATE INDEX idx_recipes_menu_item ON recipes(menu_item_id);
CREATE INDEX idx_recipes_ingredient ON recipes(ingredient_id);

-- ============================================
-- TRANSACTIONS & SALES
-- ============================================

-- Transactions (orders/tickets) - already exists, extending
-- transactions table already created in migration 002

-- Transaction items with more detail
-- transaction_items table already created in migration 002

-- ============================================
-- INVENTORY
-- ============================================

-- Current inventory levels
CREATE TABLE inventory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    ingredient_id UUID NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    quantity DECIMAL(10,3) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    batch_id VARCHAR(100),        -- For lot tracking
    expiry_date DATE,
    received_date DATE DEFAULT CURRENT_DATE,
    unit_cost DECIMAL(10,4),       -- Cost at time of purchase
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_inventory_restaurant ON inventory(restaurant_id);
CREATE INDEX idx_inventory_ingredient ON inventory(ingredient_id);
CREATE INDEX idx_inventory_expiry ON inventory(expiry_date);

-- Inventory movements (audit trail)
CREATE TABLE inventory_movements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inventory_id UUID REFERENCES inventory(id) ON DELETE SET NULL,
    ingredient_id UUID NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    movement_type VARCHAR(50) NOT NULL,  -- 'received', 'used', 'wasted', 'adjusted', 'transferred'
    quantity DECIMAL(10,3) NOT NULL,      -- Positive for in, negative for out
    unit VARCHAR(50) NOT NULL,
    reference_id UUID,                     -- Transaction ID, order ID, etc.
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_inventory_movements_restaurant ON inventory_movements(restaurant_id);
CREATE INDEX idx_inventory_movements_ingredient ON inventory_movements(ingredient_id);
CREATE INDEX idx_inventory_movements_date ON inventory_movements(created_at);

-- ============================================
-- LABOR & SCHEDULING
-- ============================================

-- Employee roles
CREATE TABLE employee_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,  -- 'Chef', 'Server', 'Bartender', 'Host'
    hourly_rate_default DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(restaurant_id, name)
);

-- Employees
CREATE TABLE employees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,  -- Optional link to user account
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    role_id UUID REFERENCES employee_roles(id) ON DELETE SET NULL,
    hourly_rate DECIMAL(10,2) NOT NULL,
    min_hours_per_week DECIMAL(5,2) DEFAULT 0,
    max_hours_per_week DECIMAL(5,2) DEFAULT 40,
    hire_date DATE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_employees_restaurant ON employees(restaurant_id);
CREATE INDEX idx_employees_active ON employees(restaurant_id, is_active);

-- Employee skills/certifications
CREATE TABLE skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,  -- 'Grill', 'Bar', 'Host', 'Food Safety Certified'
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(restaurant_id, name)
);

CREATE TABLE employee_skills (
    employee_id UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    certified_date DATE,
    expiry_date DATE,
    PRIMARY KEY (employee_id, skill_id)
);

-- Shift templates (recurring patterns)
CREATE TABLE shift_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,  -- 'Morning Prep', 'Lunch Service', 'Dinner Service'
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    required_staff INTEGER DEFAULT 1,
    required_skill_id UUID REFERENCES skills(id) ON DELETE SET NULL,
    days_of_week INTEGER[],      -- [1,2,3,4,5] = Mon-Fri
    created_at TIMESTAMP DEFAULT NOW()
);

-- Employee availability
CREATE TABLE employee_availability (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    day_of_week INTEGER NOT NULL,  -- 0=Sunday, 6=Saturday
    start_time TIME,
    end_time TIME,
    is_available BOOLEAN DEFAULT true,
    preference INTEGER DEFAULT 0,  -- -1=prefer not, 0=neutral, 1=prefer
    effective_from DATE DEFAULT CURRENT_DATE,
    effective_to DATE,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_availability_employee ON employee_availability(employee_id);

-- Time-off requests
CREATE TABLE time_off_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'approved', 'denied'
    reason TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Scheduled shifts (actual assignments)
CREATE TABLE scheduled_shifts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    employee_id UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    shift_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    role_id UUID REFERENCES employee_roles(id) ON DELETE SET NULL,
    status VARCHAR(20) DEFAULT 'scheduled',  -- 'scheduled', 'confirmed', 'completed', 'no_show'
    actual_start_time TIME,
    actual_end_time TIME,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_scheduled_shifts_restaurant ON scheduled_shifts(restaurant_id);
CREATE INDEX idx_scheduled_shifts_employee ON scheduled_shifts(employee_id);
CREATE INDEX idx_scheduled_shifts_date ON scheduled_shifts(shift_date);

-- ============================================
-- FORECASTING & ANALYTICS
-- ============================================

-- Demand forecasts (generated by ML)
CREATE TABLE demand_forecasts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    menu_item_id UUID REFERENCES menu_items(id) ON DELETE CASCADE,
    forecast_date DATE NOT NULL,
    predicted_quantity DECIMAL(10,2) NOT NULL,
    lower_bound DECIMAL(10,2),      -- 95% CI lower
    upper_bound DECIMAL(10,2),      -- 95% CI upper
    model_version VARCHAR(50),
    factors JSONB,                   -- Explainability: {"weather": 0.2, "day_of_week": 0.5}
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_forecasts_restaurant ON demand_forecasts(restaurant_id);
CREATE INDEX idx_forecasts_date ON demand_forecasts(forecast_date);
CREATE UNIQUE INDEX idx_forecasts_unique ON demand_forecasts(restaurant_id, menu_item_id, forecast_date, model_version);

-- Staffing forecasts (derived from demand)
CREATE TABLE staffing_forecasts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    forecast_date DATE NOT NULL,
    hour_of_day INTEGER NOT NULL,  -- 0-23
    predicted_covers INTEGER,
    recommended_staff INTEGER,
    role_id UUID REFERENCES employee_roles(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_staffing_forecasts_date ON staffing_forecasts(restaurant_id, forecast_date);

-- ============================================
-- PROMOTIONS & PRICING
-- ============================================

-- Promotions
CREATE TABLE promotions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    menu_item_id UUID REFERENCES menu_items(id) ON DELETE CASCADE,
    name VARCHAR(255),
    discount_type VARCHAR(20) NOT NULL,  -- 'percentage', 'fixed_amount'
    discount_value DECIMAL(10,2) NOT NULL,
    min_margin DECIMAL(5,2),              -- Floor margin to protect
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'draft',   -- 'draft', 'active', 'completed', 'cancelled'
    trigger_reason VARCHAR(100),           -- 'expiring_stock', 'low_demand', 'manual'
    expected_lift DECIMAL(5,2),            -- Predicted % increase in sales
    actual_lift DECIMAL(5,2),              -- Observed % increase
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_promotions_restaurant ON promotions(restaurant_id);
CREATE INDEX idx_promotions_dates ON promotions(start_date, end_date);

-- Price elasticity estimates (learned over time)
CREATE TABLE price_elasticity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    menu_item_id UUID REFERENCES menu_items(id) ON DELETE CASCADE,
    category_id UUID REFERENCES menu_categories(id) ON DELETE CASCADE,  -- Can store at category level
    elasticity DECIMAL(5,3) NOT NULL,  -- Typical range: 0.5 - 4.0
    confidence DECIMAL(5,3),            -- 0-1, how confident we are
    sample_size INTEGER,                -- Number of observations
    last_updated TIMESTAMP DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_elasticity_item ON price_elasticity(restaurant_id, menu_item_id) WHERE menu_item_id IS NOT NULL;
CREATE UNIQUE INDEX idx_elasticity_category ON price_elasticity(restaurant_id, category_id) WHERE category_id IS NOT NULL AND menu_item_id IS NULL;

-- ============================================
-- EXTERNAL DATA
-- ============================================

-- Weather data (for forecasting)
CREATE TABLE weather_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location VARCHAR(100) NOT NULL,  -- City or zip code
    date DATE NOT NULL,
    temp_high DECIMAL(5,2),
    temp_low DECIMAL(5,2),
    precipitation_mm DECIMAL(5,2),
    conditions VARCHAR(50),  -- 'sunny', 'cloudy', 'rainy', 'snowy'
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(location, date)
);

-- Local events (for forecasting)
CREATE TABLE local_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    event_date DATE NOT NULL,
    event_type VARCHAR(50),  -- 'sports', 'concert', 'holiday', 'festival'
    expected_impact DECIMAL(5,2),  -- Multiplier: 1.2 = +20% demand
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_events_restaurant ON local_events(restaurant_id);
CREATE INDEX idx_events_date ON local_events(event_date);

-- ============================================
-- AUDIT & EXTENSIBILITY
-- ============================================

-- Generic settings/config per restaurant (flexible key-value)
CREATE TABLE restaurant_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    setting_key VARCHAR(100) NOT NULL,
    setting_value JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(restaurant_id, setting_key)
);

-- Algorithm run logs (for debugging and audit)
CREATE TABLE algorithm_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    algorithm_name VARCHAR(100) NOT NULL,  -- 'demand_forecast', 'labor_schedule', 'promotions'
    run_started_at TIMESTAMP DEFAULT NOW(),
    run_completed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'running',  -- 'running', 'completed', 'failed'
    input_params JSONB,
    output_summary JSONB,
    error_message TEXT
);
CREATE INDEX idx_algorithm_runs_restaurant ON algorithm_runs(restaurant_id);
CREATE INDEX idx_algorithm_runs_date ON algorithm_runs(run_started_at);

-- ============================================
-- ROW LEVEL SECURITY
-- ============================================

-- Enable RLS on all tables (sample for key tables)
ALTER TABLE menu_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingredients ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees ENABLE ROW LEVEL SECURITY;
ALTER TABLE scheduled_shifts ENABLE ROW LEVEL SECURITY;
ALTER TABLE demand_forecasts ENABLE ROW LEVEL SECURITY;
ALTER TABLE promotions ENABLE ROW LEVEL SECURITY;

-- Policies would follow pattern:
-- CREATE POLICY policy_name ON table_name
-- FOR ALL TO authenticated_user
-- USING (restaurant_id = current_setting('app.current_restaurant_id')::uuid);
