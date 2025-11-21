# Implementation Plan: Delete Previous Live Notifications

## Problem Statement
When an Instagram user goes live multiple times (e.g., twice with 30min idle between), we need to delete the first notification message before sending the second one. This prevents message clutter in groups.

## Current State
- Instagram usernames tracked in `insta_links` table
- When user goes live, notifications sent to groups via `notify_live_handler`
- No tracking of sent message IDs per Instagram username per group
- Messages accumulate in groups

## Solution Overview
Track message IDs for each Instagram username in each group, then delete previous messages before sending new live notifications.

## Database Changes

### New Table: live_notification_messages
```sql
CREATE TABLE live_notification_messages (
    username text NOT NULL,
    group_id text NOT NULL,
    message_id bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    PRIMARY KEY (username, group_id)
);

CREATE INDEX idx_live_notif_username ON live_notification_messages(username);
CREATE INDEX idx_live_notif_created_at ON live_notification_messages(created_at);
```

## Code Changes

### 1. Add Model to models.py
```python
class LiveNotificationMessage(Base):
    __tablename__ = 'live_notification_messages'
    username = Column(Text, primary_key=True)
    group_id = Column(Text, primary_key=True)
    message_id = Column(BIGINT, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.now)
```

### 2. Update notify_live_handler in handlers.py
Before sending notification:
- Query `live_notification_messages` for username
- Delete all previous messages across groups
- Send new notification
- Save new `message_id` (UPSERT)

**Flow:**
1. For Instagram user going live:
2. `SELECT * FROM live_notification_messages WHERE username = ?`
3. For each record: DELETE message via Telegram API
4. Send new notification to groups
5. `INSERT/UPDATE message_id` in `live_notification_messages`

### 3. Helper Functions
```python
async def delete_previous_live_notifications(session, helper, username):
    # Query previous messages
    # Delete via telegram_helper.delete_message()
    # Handle errors silently

async def save_live_notification_message(session, username, group_id, message_id):
    # UPSERT into live_notification_messages
```

## Implementation Details

### Error Handling
- If deletion fails (message too old, already deleted), log but continue
- Don't block new message sending on deletion failures
- Clean up stale records (messages >48h old can't be deleted)

### Rate Limiting
- Telegram allows 20 messages/sec per bot
- Add small delay between deletions if needed

### Bot Permissions
- Bot must have `delete_messages` permission in groups

### Migration File
Create: `migration_live_notification_tracking.sql`

## Testing
1. Instagram user goes live → message sent
2. Same user goes live again → first message deleted, new message sent
3. Multiple groups → all previous messages deleted across groups
4. Failed deletion → new message still sent

## Rollback Plan
1. Drop `live_notification_messages` table
2. Revert handler changes
3. Messages will accumulate as before