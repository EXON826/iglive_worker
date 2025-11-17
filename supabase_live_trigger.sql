-- Supabase trigger to auto-create notification jobs when someone goes live

-- First, create the trigger function
CREATE OR REPLACE FUNCTION notify_live_stream()
RETURNS TRIGGER AS $$
BEGIN
    -- Only trigger when is_live changes from FALSE to TRUE
    IF NEW.is_live = TRUE AND (OLD.is_live = FALSE OR OLD.is_live IS NULL) THEN
        -- Insert notification job
        INSERT INTO jobs (job_type, payload, status, created_at, updated_at)
        VALUES (
            'notify_live',
            json_build_object(
                'username', NEW.username,
                'link', NEW.link,
                'last_live_at', NEW.last_live_at
            ),
            'pending',
            NOW(),
            NOW()
        );
        
        -- Log the trigger execution
        RAISE NOTICE 'Live notification job created for username: %', NEW.username;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop existing trigger if it exists
DROP TRIGGER IF EXISTS trigger_notify_live_stream ON insta_links;

-- Create the trigger
CREATE TRIGGER trigger_notify_live_stream
    AFTER UPDATE OF is_live ON insta_links
    FOR EACH ROW
    EXECUTE FUNCTION notify_live_stream();

-- Create index for better job processing performance
CREATE INDEX IF NOT EXISTS idx_jobs_type_status ON jobs(job_type, status) WHERE status = 'pending';