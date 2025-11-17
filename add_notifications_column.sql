-- Add notifications preference column to telegram_users table
ALTER TABLE telegram_users 
ADD COLUMN IF NOT EXISTS notifications_enabled BOOLEAN DEFAULT TRUE;