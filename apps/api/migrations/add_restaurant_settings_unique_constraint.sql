-- Add unique constraint to restaurant_settings
-- This ensures each restaurant can only have one value per setting_key

ALTER TABLE restaurant_settings
ADD CONSTRAINT uq_restaurant_settings_key
UNIQUE (restaurant_id, setting_key);
