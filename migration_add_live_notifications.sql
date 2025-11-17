-- Migration to add live stream notifications for premium users

CREATE OR REPLACE FUNCTION notify_live_stream()
RETURNS TRIGGER AS $$
DECLARE
    bot_token_var TEXT;
BEGIN
    IF NEW.is_live = TRUE AND (OLD.is_live = FALSE OR OLD.is_live IS NULL) THEN
        SELECT bot_token INTO bot_token_var FROM bots LIMIT 1;
        
        INSERT INTO jobs (job_type, payload, bot_token, status, created_at, updated_at)
        VALUES (
            'notify_live',
            json_build_object(
                'username', NEW.username,
                'link', NEW.link,
                'last_live_at', NEW.last_live_at
            )::text,
            bot_token_var,
            'pending',
            NOW(),
            NOW()
        );
        
        RAISE NOTICE 'Live notification job created for username: %', NEW.username;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_notify_live_stream ON insta_links;

CREATE TRIGGER trigger_notify_live_stream
    AFTER UPDATE OF is_live ON insta_links
    FOR EACH ROW
    EXECUTE FUNCTION notify_live_stream();

CREATE INDEX IF NOT EXISTS idx_jobs_type_status ON jobs(job_type, status) WHERE status = 'pending';