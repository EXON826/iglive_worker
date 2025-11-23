# promotional_handlers.py
# Handlers for the Promotional Broadcast System wizard

import logging
import json
import asyncio
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text

from models import TelegramUser, Job, SystemSettings
from telegram_helper import TelegramHelper
from config import ADMIN_IDS

logger = logging.getLogger(__name__)

# Wizard states
STATE_SELECT_TARGET = "promote:target"
STATE_AWAIT_CONTENT = "promote:content"
STATE_CONFIRM = "promote:confirm"

# Target definitions
TARGETS = {
    "all": {"name": "👥 All Users", "desc": "Send to everyone"},
    "free": {"name": "🆓 Free Users", "desc": "Users without Premium"},
    "premium": {"name": "💎 Premium Users", "desc": "Active Premium subscribers"},
    "inactive": {"name": "💤 Inactive Users", "desc": "No activity for 7+ days"},
    "en": {"name": "🇬🇧 English Users", "desc": "Language set to English"},
    "ru": {"name": "🇷🇺 Russian Users", "desc": "Language set to Russian"},
    "es": {"name": "🇪🇸 Spanish Users", "desc": "Language set to Spanish"},
}

async def promote_command_handler(session: Session, payload: dict):
    """
    Step 1: Start the promotion wizard.
    Command: /promote
    """
    try:
        message = payload.get('message', {})
        from_user = message.get('from', {})
        sender_id = from_user.get('id')
        
        if not sender_id:
            return

        # Authorization check
        if sender_id not in ADMIN_IDS:
            return

        helper = TelegramHelper()
        
        text = "📢 *Promotional Broadcast Wizard*\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        text += "Select your target audience:"

        buttons = []
        row = []
        for key, info in TARGETS.items():
            row.append({"text": info['name'], "callback_data": f"promote:target:{key}"})
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
            
        buttons.append([{"text": "❌ Cancel", "callback_data": "promote:cancel"}])

        await helper.send_message(sender_id, text, parse_mode="Markdown", reply_markup={"inline_keyboard": buttons})
        
        # Save state (using SystemSettings as a simple KV store for wizard state)
        # Key format: wizard:user_id
        state_key = f"wizard:{sender_id}"
        state_data = json.dumps({"step": STATE_SELECT_TARGET})
        
        existing = session.query(SystemSettings).filter_by(key=state_key).first()
        if existing:
            existing.value = state_data
            existing.updated_at = datetime.now(timezone.utc)
        else:
            session.add(SystemSettings(key=state_key, value=state_data))
        session.commit()

    except Exception as e:
        logger.error(f"Error in promote_command_handler: {e}", exc_info=True)


async def promote_callback_handler(session: Session, payload: dict):
    """
    Handle wizard callbacks.
    """
    try:
        callback_query = payload.get('callback_query', {})
        data = callback_query.get('data', '')
        from_user = callback_query.get('from', {})
        sender_id = from_user.get('id')
        message = callback_query.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        message_id = message.get('message_id')

        if not sender_id:
            return

        helper = TelegramHelper()

        if data == "promote:cancel":
            # Clear state
            session.query(SystemSettings).filter_by(key=f"wizard:{sender_id}").delete()
            session.commit()
            await helper.edit_message_text(chat_id, message_id, "❌ Promotion cancelled.")
            return

        if data.startswith("promote:target:"):
            target_key = data.split(":")[-1]
            target_info = TARGETS.get(target_key)
            
            if not target_info:
                return

            text = f"🎯 Target: *{target_info['name']}*\n"
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            text += "Send the content you want to broadcast.\n"
            text += "✅ *Supported:* Text, Photo, Video\n"
            text += "📝 *Formatting:* Markdown is supported"
            
            await helper.edit_message_text(chat_id, message_id, text, parse_mode="Markdown")
            
            # Update state
            state_key = f"wizard:{sender_id}"
            state_data = json.dumps({
                "step": STATE_AWAIT_CONTENT,
                "target": target_key
            })
            
            existing = session.query(SystemSettings).filter_by(key=state_key).first()
            if existing:
                existing.value = state_data
            else:
                session.add(SystemSettings(key=state_key, value=state_data))
            session.commit()

        elif data == "promote:confirm":
            # Fetch state to get payload
            state_key = f"wizard:{sender_id}"
            state_entry = session.query(SystemSettings).filter_by(key=state_key).first()
            
            if not state_entry:
                await helper.send_message(sender_id, "⚠️ Session expired. Start over with /promote")
                return
                
            state = json.loads(state_entry.value)
            
            # Create the job
            new_job = Job(
                job_type='broadcast_message',
                payload=json.dumps({
                    'target': state['target'],
                    'content': state['content']
                }),
                status='pending'
            )
            session.add(new_job)
            
            # Clear state
            session.delete(state_entry)
            session.commit()
            
            await helper.edit_message_text(chat_id, message_id, "🚀 *Campaign Queued!*\n\nYour broadcast is being processed.")

    except Exception as e:
        logger.error(f"Error in promote_callback_handler: {e}", exc_info=True)


async def promote_content_handler(session: Session, payload: dict):
    """
    Handle content input for the wizard.
    """
    try:
        message = payload.get('message', {})
        from_user = message.get('from', {})
        sender_id = from_user.get('id')
        
        if not sender_id:
            return

        # Check if user is in wizard state
        state_key = f"wizard:{sender_id}"
        state_entry = session.query(SystemSettings).filter_by(key=state_key).first()
        
        if not state_entry:
            return # Not in wizard, ignore
            
        state = json.loads(state_entry.value)
        if state.get('step') != STATE_AWAIT_CONTENT:
            return

        helper = TelegramHelper()
        
        # Extract content
        content = {}
        if 'text' in message:
            content['type'] = 'text'
            content['text'] = message['text']
        elif 'photo' in message:
            content['type'] = 'photo'
            content['file_id'] = message['photo'][-1]['file_id'] # Best quality
            content['caption'] = message.get('caption', '')
        elif 'video' in message:
            content['type'] = 'video'
            content['file_id'] = message['video']['file_id']
            content['caption'] = message.get('caption', '')
        else:
            await helper.send_message(sender_id, "⚠️ Unsupported media type. Please send Text, Photo, or Video.")
            return

        # Estimate reach
        target = state['target']
        count_query = get_target_query(target, count=True)
        estimated_reach = session.execute(text(count_query)).scalar()

        # Confirmation
        confirm_text = "📢 *Confirm Broadcast*\n"
        confirm_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        confirm_text += f"🎯 *Target:* {TARGETS[target]['name']}\n"
        confirm_text += f"👥 *Est. Reach:* ~{estimated_reach} users\n"
        confirm_text += f"📄 *Type:* {content['type'].title()}\n\n"
        confirm_text += "Ready to send?"

        buttons = {
            "inline_keyboard": [
                [{"text": "🚀 Send Now", "callback_data": "promote:confirm"}],
                [{"text": "❌ Cancel", "callback_data": "promote:cancel"}]
            ]
        }
        
        await helper.send_message(sender_id, confirm_text, parse_mode="Markdown", reply_markup=buttons)
        
        # Update state
        state['step'] = STATE_CONFIRM
        state['content'] = content
        state_entry.value = json.dumps(state)
        session.commit()

    except Exception as e:
        logger.error(f"Error in promote_content_handler: {e}", exc_info=True)


def get_target_query(target_key: str, count: bool = False) -> str:
    """Helper to generate SQL query for targeting."""
    select_part = "SELECT COUNT(*)" if count else "SELECT id, first_name, language"
    base_query = f"{select_part} FROM telegram_users"
    
    if target_key == "all":
        return base_query
    elif target_key == "free":
        return f"{base_query} WHERE subscription_end IS NULL OR subscription_end < NOW()"
    elif target_key == "premium":
        return f"{base_query} WHERE subscription_end > NOW()"
    elif target_key == "inactive":
        return f"{base_query} WHERE last_seen < NOW() - INTERVAL '7 days'"
    elif target_key in ["en", "ru", "es"]:
        return f"{base_query} WHERE language = '{target_key}'"
    
    return base_query


async def execute_broadcast_job(session: Session, payload: dict):
    """
    Executes the broadcast job with targeting and rich media.
    """
    try:
        target = payload.get('target', 'all')
        content = payload.get('content', {})
        
        if not content:
            logger.error("No content in broadcast payload")
            return

        # Get target users
        query = get_target_query(target)
        users = session.execute(text(query)).fetchall()
        
        helper = TelegramHelper()
        success_count = 0
        fail_count = 0
        
        logger.info(f"Starting broadcast to {len(users)} users (Target: {target})")
        
        for row in users:
            user_id = row[0]
            try:
                if content['type'] == 'text':
                    await helper.send_message(user_id, content['text'], parse_mode="Markdown")
                elif content['type'] == 'photo':
                    await helper.send_photo(user_id, content['file_id'], caption=content.get('caption'), parse_mode="Markdown")
                elif content['type'] == 'video':
                    await helper.send_video(user_id, content['file_id'], caption=content.get('caption'), parse_mode="Markdown")
                
                success_count += 1
                await asyncio.sleep(0.05) # 20 messages per second max
            except Exception as e:
                # logger.error(f"Failed to send to {user_id}: {e}")
                fail_count += 1
        
        logger.info(f"Broadcast finished. Success: {success_count}, Failed: {fail_count}")

    except Exception as e:
        logger.error(f"Error in execute_broadcast_job: {e}", exc_info=True)
        raise
