-- Migration: Add live notification message tracking
-- Purpose: Track sent live notification messages to delete previous ones

-- Create the live_notification_messages table
CREATE TABLE live_notification_messages (
    username text NOT NULL,
    group_id text NOT NULL,
    message_id bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    PRIMARY KEY (username, group_id)
);

-- Create indexes for efficient queries
CREATE INDEX idx_live_notif_username ON live_notification_messages(username);
CREATE INDEX idx_live_notif_created_at ON live_notification_messages(created_at);

-- Add cleanup function to remove old records (messages older than 48h can't be deleted by Telegram)
CREATE OR REPLACE FUNCTION cleanup_old_live_notifications()
RETURNS void AS $$
BEGIN
    DELETE FROM live_notification_messages 
    WHERE created_at < now() - interval '48 hours';
END;
$$ LANGUAGE plpgsql;

-- Optional: Create a scheduled job to run cleanup (uncomment if you want automatic cleanup)
-- SELECT cron.schedule('cleanup-live-notifications', '0 */6 * * *', 'SELECT cleanup_old_live_notifications();');