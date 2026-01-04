-- Row-Level Security (RLS) Policies for Flux
-- Run this script after the initial migration to enable multi-tenant isolation

-- Enable RLS on restaurants table
ALTER TABLE restaurants ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own restaurants
CREATE POLICY restaurants_user_isolation ON restaurants
    FOR ALL
    USING (owner_id = current_setting('app.current_user_id', true)::uuid);

-- Enable RLS on data_uploads table
ALTER TABLE data_uploads ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see uploads for their own restaurants
CREATE POLICY data_uploads_user_isolation ON data_uploads
    FOR ALL
    USING (
        restaurant_id IN (
            SELECT id FROM restaurants
            WHERE owner_id = current_setting('app.current_user_id', true)::uuid
        )
    );

-- Note: The application must set the session variable before queries:
-- SET app.current_user_id = 'user-uuid-here';
--
-- For the API service role (used by FastAPI), we need to bypass RLS:
-- This is typically done by creating a service role that has BYPASSRLS privilege
-- or by using the postgres superuser for migrations/admin tasks.
