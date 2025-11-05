# worker/handlers.py

import os
import logging
import asyncio
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from models import TelegramUser, ChatGroup
from telegram_helper import TelegramHelper
from instagram_checker import get_currently_live_users

# --- Logging Setup ---
logger = logging.getLogger(__name__)

# --- Constants ---
# In a real app, these would come from a config file
BOT_TOKEN = os.environ.get('BOT_TOKEN')
BOT_API_ID = os.environ.get('BOT_API_ID')
BOT_API_HASH = os.environ.get('BOT_API_HASH')


# --- Group Join Configuration ---
REQUIRED_GROUP_URL = "https://t.me/+FBDgBcLD1C5jN2Jk"
REQUIRED_GROUP_ID = -1002891494486


def is_new_day_for_user(user: TelegramUser) -> bool:
    """Check if it's a new day for the user considering timezone."""
    if not user.last_seen:
        return True
    
    now = datetime.now(timezone.utc)
    last_seen_utc = user.last_seen.replace(tzinfo=timezone.utc) if user.last_seen.tzinfo is None else user.last_seen
    
    # Simple daily reset at UTC midnight
    return now.date() > last_seen_utc.date()

async def send_user_feedback(user_id: int, message: str):
    """Send feedback to user with error handling."""
    logger.info(f"FEEDBACK to {user_id}: {message}")
    try:
        helper = TelegramHelper()
        await helper.send_message(user_id, message)
        logger.info(f"Successfully sent feedback to {user_id}")
    except Exception as e:
        logger.error(f"Failed to send feedback to {user_id}: {e}", exc_info=True)


async def send_main_menu(user_id: int, prefix_message: str = ""):
    """Send the main menu to a user."""
    try:
        menu_text = f"{prefix_message}🎉 Welcome to IGLiveZBot! 🎉\n\n"
        menu_text += "📱 Check who's live on Instagram\n"
        menu_text += "💰 Manage your points and subscription\n"
        menu_text += "🎁 Invite friends for bonus points\n\n"
        menu_text += "Use the buttons below to get started:"

        buttons = {
            "inline_keyboard": [
                [
                    {"text": "🔴 Check LIVEs", "callback_data": "check_live"},
                    {"text": "👤 My Account", "callback_data": "my_account"}
                ]
            ]
        }
        
        helper = TelegramHelper()
        await helper.send_message(user_id, menu_text, reply_markup=buttons)
        logger.info(f"Successfully sent main menu to {user_id}")
    except Exception as e:
        logger.error(f"Failed to send main menu to {user_id}: {e}", exc_info=True)
        raise


async def start_handler(session: Session, payload: dict):
    """
    Handles the logic for a /start command from a user.
    This function is called by the worker when it processes a 'start_command' job.
    """
    try:
        message = payload.get('message', {})
        from_user = message.get('from', {})
        sender_id = from_user.get('id')
        
        if not sender_id:
            logger.error("Could not determine sender_id from payload.")
            return

        # --- Group Membership Check ---
        helper = TelegramHelper()
        is_member = await helper.is_user_in_group(REQUIRED_GROUP_ID, sender_id)
        if not is_member:
            logger.info(f"User {sender_id} is not in the required group. Sending join prompt.")
            join_button = {
                "inline_keyboard": [[{"text": "Join Group", "url": REQUIRED_GROUP_URL}]]
            }
            await helper.send_message(
                sender_id,
                "You must join our group to use this bot.",
                reply_markup=join_button
            )
            return

        user = session.query(TelegramUser).filter_by(id=sender_id).first()
        
        prefix_message = ""
        if not user:
            # --- Handle New User & Referrals ---
            referred_by_id = None
            text = message.get('text', '')
            if text and len(text.split()) > 1:
                try:
                    referred_by_id = int(text.split()[1])
                    if referred_by_id == sender_id: # Can't refer self
                        referred_by_id = None
                except (ValueError, IndexError):
                    referred_by_id = None

            user = TelegramUser(
                id=sender_id,
                username=from_user.get('username'),
                first_name=from_user.get('first_name'),
                points=10,
                last_seen=datetime.now(timezone.utc),
                referred_by_id=referred_by_id
            )
            session.add(user)
            session.commit()
            prefix_message = f"Welcome, {user.first_name}! You have been given 10 points.\n\n"
            logger.info(f"New user created: {user.id} (@{user.username})")

            if referred_by_id:
                referrer = session.query(TelegramUser).filter_by(id=referred_by_id).first()
                if referrer:
                    referrer.points += 10
                    session.commit()
                    await send_user_feedback(
                        referrer.id,
                        f"🎉 {user.first_name} joined using your referral link! You've earned 10 points."
                    )
                    logger.info(f"Awarded 10 referral points to {referrer.id}")

        elif is_new_day_for_user(user):
            # --- Handle Daily Point Reset ---
            user.points = 10
            user.last_seen = datetime.now(timezone.utc)
            session.commit()
            prefix_message = "Your points have been reset to 10 for the day!\n\n"
            logger.info(f"Reset daily points for user {user.id}")
        else:
            # Update last_seen for existing user
            user.last_seen = datetime.now(timezone.utc)
            session.commit()

        # --- Send Main Menu ---
        logger.info(f"Sending main menu to {user.id} with prefix: '{prefix_message}'")
        await send_main_menu(user.id, prefix_message)

    except Exception as e:
        logger.error(f"Error in start_handler for user {sender_id}: {e}", exc_info=True)
        session.rollback()
        raise


async def my_account_handler(session: Session, payload: dict):
    """
    Handles the logic for a /my_account command from a user.
    """
    try:
        callback_query = payload.get('callback_query', {})
        from_user = callback_query.get('from', {})
        sender_id = from_user.get('id')

        if not sender_id:
            logger.error("Could not determine sender_id from payload.")
            return

        user = session.query(TelegramUser).filter_by(id=sender_id).first()
        if not user:
            logger.warning(f"User {sender_id} not found for my_account.")
            await send_user_feedback(sender_id, "Please use /start first to register.")
            return

        # Format account details message
        is_unlimited = user.subscription_end and user.subscription_end > datetime.now(timezone.utc)
        account_text = f"👤 Account Details\n\n"
        account_text += f"Name: {user.first_name}\n"
        account_text += f"Username: @{user.username or 'Not set'}\n"
        account_text += f"Points: {'♾️ Unlimited' if is_unlimited else user.points}\n"
        
        if is_unlimited:
            account_text += f"Subscription: Active until {user.subscription_end.strftime('%Y-%m-%d')}\n"
        
        helper = TelegramHelper()
        buttons = {
            "inline_keyboard": [
                [
                    {"text": "⬅️ Back", "callback_data": "back"}
                ]
            ]
        }
        await helper.send_message(sender_id, account_text, reply_markup=buttons)
        logger.info(f"Sent account details to user {user.id}")

    except Exception as e:
        logger.error(f"Error in my_account_handler for user {sender_id}: {e}", exc_info=True)
        raise


async def check_live_handler(session: Session, payload: dict):
    """
    Handles the logic for a /check_live command from a user.
    """
    try:
        callback_query = payload.get('callback_query', {})
        from_user = callback_query.get('from', {})
        sender_id = from_user.get('id')

        if not sender_id:
            logger.error("Could not determine sender_id from payload.")
            return

        user = session.query(TelegramUser).filter_by(id=sender_id).first()
        if not user:
            logger.warning(f"User {sender_id} not found for check_live.")
            await send_user_feedback(sender_id, "Please use /start first to register.")
            return

        # Deduct points if not unlimited
        is_unlimited = user.subscription_end and user.subscription_end > datetime.now(timezone.utc)
        if not is_unlimited:
            if user.points > 0:
                user.points -= 1
                session.commit()
            else:
                logger.info(f"User {user.id} has no points to check live users.")
                await send_user_feedback(sender_id, "❌ You have no points left. Your points will reset tomorrow or upgrade to unlimited!")
                return
        
        # Get currently live users from database (updated by instagram_checker)
        live_users = await get_currently_live_users(session)
        
        # Format message with live users
        if live_users:
            live_message = "📱 Currently Live on Instagram:\n\n"
            live_message += "Note: This list is updated every 10 minutes.\n\n"
            for user_data in live_users[:10]:  # Show max 10 users
                username = user_data['username']
                total_lives = user_data.get('total_lives', 0)
                link = user_data.get('link', f"https://instagram.com/{username.lstrip('@')}")
                live_message += f"🔴 {username}\n"
                live_message += f"   Total Lives: {total_lives} | [Watch]({link})\n\n"
            
            if len(live_users) > 10:
                live_message += f"...and {len(live_users) - 10} more\n\n"
        else:
            live_message = "📱 Currently Live on Instagram:\n\n"
            live_message += "No one is live right now. 😴\n\n"
        
        live_message += f"Points remaining: {'♾️ Unlimited' if is_unlimited else user.points}"
        
        helper = TelegramHelper()
        buttons = {
            "inline_keyboard": [
                [
                    {"text": "🔄 Refresh", "callback_data": "check_live"},
                    {"text": "⬅️ Back", "callback_data": "back"}
                ]
            ]
        }
        await helper.send_message(sender_id, live_message, parse_mode="Markdown", reply_markup=buttons)
        logger.info(f"User {user.id} checked for live users. Found {len(live_users)} live. Points remaining: {user.points}")

    except Exception as e:
        logger.error(f"Error in check_live_handler for user {sender_id}: {e}", exc_info=True)
        session.rollback()
        raise


async def join_request_handler(session: Session, payload: dict):
    """
    Handles a chat_join_request update from Telegram.
    """
    try:
        join_request = payload.get('chat_join_request', {})
        chat = join_request.get('chat', {})
        user = join_request.get('from', {})
        
        chat_id = chat.get('id')
        user_id = user.get('id')

        if not chat_id or not user_id:
            logger.error("Could not determine chat_id or user_id from join request payload.")
            return

        # For the MVP, we will auto-approve join requests.
        helper = TelegramHelper()
        await helper.approve_chat_join_request(chat_id, user_id)

        # Log the action to the database
        logger.info(f"Auto-approved join request for user {user_id} in chat {chat_id}.")

    except Exception as e:
        logger.error(f"Error in join_request_handler: {e}", exc_info=True)
        raise


async def init_handler(session: Session, payload: dict):
    """
    Handles the /init command sent in a group chat.
    Registers the group and the admin.
    """
    try:
        message = payload.get('message', {})
        chat = message.get('chat', {})
        from_user = message.get('from', {})
        
        chat_id = chat.get('id')
        user_id = from_user.get('id')
        chat_title = chat.get('title')

        if not chat_id or not user_id:
            logger.error("Could not determine chat_id or user_id from /init payload.")
            return

        # 1. Check if the user is an admin in the group
        helper = TelegramHelper()
        is_admin = await helper.is_user_admin(chat_id, user_id)
        if not is_admin:
            await helper.send_message(chat_id, "You must be an admin of this group to use the /init command.")
            logger.warning(f"User {user_id} tried to /init in {chat_id} but is not an admin.")
            return

        # 2. Check if the bot itself is an admin
        bot_is_admin = await helper.is_bot_admin(chat_id)
        if not bot_is_admin:
            await helper.send_message(chat_id, "This bot must be an administrator in this group to function correctly.")
            logger.warning(f"Bot is not an admin in chat {chat_id}. Cannot complete /init.")
            return

        # 3. Register the group and admin
        group = session.query(ChatGroup).filter_by(chat_id=str(chat_id)).first()
        if group:
            group.admin_user_id = user_id
            group.is_active = True
            group.title = chat_title
        else:
            group = ChatGroup(
                chat_id=str(chat_id),
                admin_user_id=user_id,
                title=chat_title,
                is_active=True
            )
            session.add(group)
        
        session.commit()
        logger.info(f"Group {chat_id} ('{chat_title}') initialized/updated by admin {user_id}.")
        await helper.send_message(chat_id, f"✅ This group has been successfully registered. The admin is {from_user.get('first_name')}.")

    except Exception as e:
        logger.error(f"Error in init_handler for chat {chat_id}: {e}", exc_info=True)
        session.rollback()
        raise


async def activate_handler(session: Session, payload: dict):
    """
    Handles the /activate command to grant a user unlimited points.
    """
    try:
        message = payload.get('message', {})
        chat = message.get('chat', {})
        from_user = message.get('from', {})
        
        chat_id = chat.get('id')
        user_id = from_user.get('id')

        if not chat_id or not user_id:
            logger.error("Could not determine chat_id or user_id from /activate payload.")
            return

        # 1. Find the group in the database
        group = session.query(ChatGroup).filter_by(chat_id=str(chat_id), is_active=True).first()
        if not group:
            await send_user_feedback(user_id, "This group is not registered. Please use /init in the group first.")
            return

        # 2. Check if the user is the registered admin of this group
        if group.admin_user_id != user_id:
            await send_user_feedback(user_id, "You are not the registered admin for this group.")
            return
            
        # 3. Grant unlimited points to the user
        user = session.query(TelegramUser).filter_by(id=user_id).first()
        if not user:
            # This should be rare, as they likely used /start already
            logger.warning(f"User {user_id} used /activate but was not in the users table. Creating new entry.")
            user = TelegramUser(id=user_id, username=from_user.get('username'), first_name=from_user.get('first_name'))
            session.add(user)

        # Set subscription_end to a far-future date to represent "unlimited"
        user.subscription_end = datetime(2099, 12, 31, tzinfo=timezone.utc)
        session.commit()

        logger.info(f"User {user_id} has been granted unlimited points via group {chat_id}.")
        await send_user_feedback(user_id, "🎉 Congratulations! You now have unlimited points.")

    except Exception as e:
        logger.error(f"Error in activate_handler for user {user_id}: {e}", exc_info=True)
        session.rollback()
        raise


async def back_handler(session: Session, payload: dict):
    """
    Handles the logic for a 'back' button press, sending the main menu.
    """
    try:
        callback_query = payload.get('callback_query', {})
        from_user = callback_query.get('from', {})
        sender_id = from_user.get('id')

        if not sender_id:
            logger.error("Could not determine sender_id from back_handler payload.")
            return
        
        await send_main_menu(sender_id, prefix_message="⬅️ Main Menu\n\n")
        logger.info(f"Sent main menu to {sender_id} via back button.")

    except Exception as e:
        sender_id = payload.get('callback_query', {}).get('from', {}).get('id')
        logger.error(f"Error in back_handler for user {sender_id}: {e}", exc_info=True)
        # Do not re-raise, as it would mark the job as failed. Just log it.


async def broadcast_message_handler(session: Session, payload: dict):
    """
    Handles a broadcast_message job, sending a message to all active groups.
    """
    try:
        message_text = payload.get('text')
        if not message_text:
            logger.error("Broadcast job is missing 'text' in payload.")
            return

        # In a real app, you'd get this from a 'managed_groups' table.
        # For the MVP, we can hardcode a list or fetch from ChatGroup.
        active_groups = session.query(ChatGroup).filter_by(is_active=True).all()
        
        if not active_groups:
            logger.info("No active groups to broadcast to.")
            return

        helper = TelegramHelper()
        for group in active_groups:
            try:
                chat_id = int(group.chat_id)
                await helper.send_message(chat_id, message_text)
                logger.info(f"Broadcasted message to group {chat_id}.")
                # Implement rate limiting
                await asyncio.sleep(1) # Simple 1-second delay between messages
            except ValueError:
                logger.warning(f"Could not convert chat_id '{group.chat_id}' to int. Skipping.")
            except Exception as e:
                logger.error(f"Failed to broadcast to group {group.chat_id}: {e}")

    except Exception as e:
        logger.error(f"Error in broadcast_message_handler: {e}", exc_info=True)
        raise