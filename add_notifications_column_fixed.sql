-- Add notifications preference column to telegram_users table (PostgreSQL syntax)
ALTER TABLE telegram_users 
ADD COLUMN notifications_enabled BOOLEAN DEFAULT TRUE;