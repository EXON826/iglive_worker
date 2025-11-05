# worker/handlers_improved.py
# Improved UI/UX version with better formatting, emojis, and user experience

import os
import logging
import asyncio
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from models import TelegramUser, ChatGroup
from telegram_helper import TelegramHelper
from instagram_checker import get_currently_live_users

logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
BOT_API_ID = os.environ.get('BOT_API_ID')
BOT_API_HASH = os.environ.get('BOT_API_HASH')

REQUIRED_GROUP_URL = "https://t.me/+FBDgBcLD1C5jN2Jk"
REQUIRED_GROUP_ID = -1002891494486


def is_new_day_for_user(user: TelegramUser) -> bool:
    """Check if it's a new day for the user considering timezone."""
    if not user.last_seen:
        return True
    
    now = datetime.now(timezone.utc)
    last_seen_utc = user.last_seen.replace(tzinfo=timezone.utc) if user.last_seen.tzinfo is None else user.last_seen
    
    return now.date() > last_seen_utc.date()


async def send_user_feedback(user_id: int, message: str):
    """Send feedback to user with error handling."""
    logger.info(f"FEEDBACK to {user_id}: {message}")
    try:
        helper = TelegramHelper()
        await helper.send_message(user_id, message, parse_mode="Markdown")
        logger.info(f"Successfully sent feedback to {user_id}")
    except Exception as e:
        logger.error(f"Failed to send feedback to {user_id}: {e}", exc_info=True)


async def send_main_menu(user_id: int, prefix_message: str = "", username: str = None):
    """Send the main menu to a user with improved UI."""
    try:
        # Greeting personalization
        greeting = f"Hey {username}! 👋" if username else "Welcome back! 👋"
        
        menu_text = f"{prefix_message}{greeting}\n\n"
        menu_text += "╔═══════════════════════════╗\n"
        menu_text += "║  🌟 *IGLiveZBot* 🌟  ║\n"
        menu_text += "╚═══════════════════════════╝\n\n"
        menu_text += "🔴 *Track Instagram Live Streams*\n"
        menu_text += "   See who's live in real-time\n\n"
        menu_text += "💎 *Smart Points System*\n"
        menu_text += "   Get 10 free points daily\n\n"
        menu_text += "🎁 *Refer & Earn*\n"
        menu_text += "   Get 10 bonus points per referral\n\n"
        menu_text += "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        menu_text += "Choose an option below to continue:"

        buttons = {
            "inline_keyboard": [
                [
                    {"text": "🔴 Check Live", "callback_data": "check_live"}
                ],
                [
                    {"text": "👤 My Account", "callback_data": "my_account"},
                    {"text": "🎁 Referrals", "callback_data": "referrals"}
                ],
                [
                    {"text": "ℹ️ Help", "callback_data": "help"}
                ]
            ]
        }
        
        helper = TelegramHelper()
        await helper.send_message(user_id, menu_text, parse_mode="Markdown", reply_markup=buttons)
        logger.info(f"Successfully sent main menu to {user_id}")
    except Exception as e:
        logger.error(f"Failed to send main menu to {user_id}: {e}", exc_info=True)
        raise


async def start_handler(session: Session, payload: dict):
    """Handles the /start command with improved welcome experience."""
    try:
        message = payload.get('message', {})
        from_user = message.get('from', {})
        sender_id = from_user.get('id')
        
        if not sender_id:
            logger.error("Could not determine sender_id from payload.")
            return

        # Group membership check with improved UI
        helper = TelegramHelper()
        is_member = await helper.is_user_in_group(REQUIRED_GROUP_ID, sender_id)
        if not is_member:
            logger.info(f"User {sender_id} is not in the required group. Sending join prompt.")
            join_text = "🚫 *Access Required*\n\n"
            join_text += "To use this bot, you need to join our community group first.\n\n"
            join_text += "✨ *Benefits of joining:*\n"
            join_text += "  • Track Instagram lives 24/7\n"
            join_text += "  • Get instant notifications\n"
            join_text += "  • Daily free points\n"
            join_text += "  • Exclusive tips & tricks\n\n"
            join_text += "👇 Click the button below to join now!"
            
            join_button = {
                "inline_keyboard": [[{"text": "✅ Join Community Group", "url": REQUIRED_GROUP_URL}]]
            }
            await helper.send_message(
                sender_id,
                join_text,
                parse_mode="Markdown",
                reply_markup=join_button
            )
            return

        user = session.query(TelegramUser).filter_by(id=sender_id).first()
        
        prefix_message = ""
        username = from_user.get('first_name', 'there')
        
        if not user:
            # New user registration
            referred_by_id = None
            text = message.get('text', '')
            if text and len(text.split()) > 1:
                try:
                    referred_by_id = int(text.split()[1])
                    if referred_by_id == sender_id:
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
            
            prefix_message = "🎉 *Welcome to IGLiveZBot!*\n\n"
            prefix_message += f"Hey {username}! Great to have you here.\n\n"
            prefix_message += "🎁 *Starter Bonus:* +10 Points\n"
            if referred_by_id:
                prefix_message += "🔗 *Referral Bonus:* Applied\n"
            prefix_message += "\n"
            
            logger.info(f"New user created: {user.id} (@{user.username})")

            if referred_by_id:
                referrer = session.query(TelegramUser).filter_by(id=referred_by_id).first()
                if referrer:
                    referrer.points += 10
                    session.commit()
                    
                    referrer_msg = f"🎊 *Referral Success!*\n\n"
                    referrer_msg += f"{username} just joined using your referral link!\n\n"
                    referrer_msg += "💰 *Reward:* +10 Points\n"
                    referrer_msg += f"💎 *New Balance:* {referrer.points} points"
                    
                    await send_user_feedback(referrer.id, referrer_msg)
                    logger.info(f"Awarded 10 referral points to {referrer.id}")

        elif is_new_day_for_user(user):
            # Daily reset
            user.points = 10
            user.last_seen = datetime.now(timezone.utc)
            session.commit()
            
            prefix_message = "🌅 *Good Morning!*\n\n"
            prefix_message += "Your daily points have been refreshed!\n\n"
            prefix_message += "💎 *Daily Bonus:* +10 Points\n\n"
            
            logger.info(f"Reset daily points for user {user.id}")
        else:
            # Returning user
            user.last_seen = datetime.now(timezone.utc)
            session.commit()

        await send_main_menu(user.id, prefix_message, username)

    except Exception as e:
        logger.error(f"Error in start_handler for user {sender_id}: {e}", exc_info=True)
        session.rollback()
        raise


async def my_account_handler(session: Session, payload: dict):
    """Displays account details with improved formatting."""
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
            await send_user_feedback(sender_id, "❌ Please use /start first to register.")
            return

        is_unlimited = user.subscription_end and user.subscription_end > datetime.now(timezone.utc)
        
        # Create visual account card
        account_text = "┏━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        account_text += "┃  👤 *YOUR ACCOUNT*  ┃\n"
        account_text += "┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        
        account_text += f"👤 *Name:* {user.first_name}\n"
        account_text += f"🆔 *Username:* @{user.username or 'Not set'}\n"
        account_text += f"🔢 *User ID:* `{user.id}`\n"
        account_text += f"📅 *Joined:* {user.last_seen.strftime('%b %d, %Y') if user.last_seen else 'Unknown'}\n\n"
        
        account_text += "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
        
        if is_unlimited:
            account_text += "💎 *PREMIUM STATUS*\n\n"
            account_text += f"✅ Unlimited Checks\n"
            account_text += f"📅 Valid Until: {user.subscription_end.strftime('%b %d, %Y')}\n"
        else:
            account_text += "💰 *POINTS BALANCE*\n\n"
            account_text += f"💎 Current: *{user.points} points*\n"
            account_text += f"🔄 Resets: Daily at midnight UTC\n"
            account_text += f"✨ Cost: 1 point per check\n"
        
        account_text += "\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
        account_text += "💡 *Tip:* Refer friends to earn bonus points!"
        
        helper = TelegramHelper()
        buttons = {
            "inline_keyboard": [
                [
                    {"text": "🎁 Get Referral Link", "callback_data": "referrals"}
                ],
                [
                    {"text": "⬅️ Back to Menu", "callback_data": "back"}
                ]
            ]
        }
        await helper.send_message(sender_id, account_text, parse_mode="Markdown", reply_markup=buttons)
        logger.info(f"Sent account details to user {user.id}")

    except Exception as e:
        logger.error(f"Error in my_account_handler for user {sender_id}: {e}", exc_info=True)
        raise


async def check_live_handler(session: Session, payload: dict):
    """Displays currently live Instagram users with improved UI."""
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
            await send_user_feedback(sender_id, "❌ Please use /start first to register.")
            return

        # Check points/subscription
        is_unlimited = user.subscription_end and user.subscription_end > datetime.now(timezone.utc)
        if not is_unlimited:
            if user.points > 0:
                user.points -= 1
                session.commit()
            else:
                no_points_msg = "⚠️ *No Points Left!*\n\n"
                no_points_msg += "You've used all your points for today.\n\n"
                no_points_msg += "🔄 *Points reset daily at midnight UTC*\n\n"
                no_points_msg += "💡 *Get more points:*\n"
                no_points_msg += "  • Wait for daily reset\n"
                no_points_msg += "  • Refer friends (+10 each)\n"
                no_points_msg += "  • Upgrade to unlimited\n"
                
                logger.info(f"User {user.id} has no points left.")
                await send_user_feedback(sender_id, no_points_msg)
                return
        
        # Get live users
        live_users = await get_currently_live_users(session)
        
        # Format the live users message
        if live_users:
            live_message = "┏━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            live_message += "┃  🔴 *LIVE NOW*  ┃\n"
            live_message += "┗━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
            live_message += f"Found *{len(live_users)}* live stream{'s' if len(live_users) != 1 else ''}!\n\n"
            
            for idx, user_data in enumerate(live_users[:10], 1):
                username = user_data['username']
                total_lives = user_data.get('total_lives', 0)
                link = user_data.get('link', f"https://instagram.com/{username.lstrip('@')}")
                
                live_message += f"┌─ Stream #{idx}\n"
                live_message += f"│ 🔴 *{username}*\n"
                live_message += f"│ 📊 Total Lives: {total_lives}\n"
                live_message += f"│ 🔗 [Watch Live]({link})\n"
                live_message += "└───────────────\n\n"
            
            if len(live_users) > 10:
                live_message += f"_...and {len(live_users) - 10} more!_\n\n"
            
            live_message += "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        else:
            live_message = "┏━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            live_message += "┃  🔴 *LIVE NOW*  ┃\n"
            live_message += "┗━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
            live_message += "😴 No one is live right now.\n\n"
            live_message += "💡 *Tip:* Live streams are tracked\n"
            live_message += "   in real-time. Check back soon!\n\n"
            live_message += "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        
        # Add points/subscription info
        if is_unlimited:
            live_message += f"\n💎 *Status:* Premium (Unlimited)\n"
        else:
            live_message += f"\n💰 *Points Left:* {user.points}\n"
        
        live_message += f"⏰ *Updated:* {datetime.now(timezone.utc).strftime('%I:%M %p UTC')}"
        
        helper = TelegramHelper()
        buttons = {
            "inline_keyboard": [
                [
                    {"text": "🔄 Refresh", "callback_data": "check_live"}
                ],
                [
                    {"text": "⬅️ Back to Menu", "callback_data": "back"}
                ]
            ]
        }
        await helper.send_message(sender_id, live_message, parse_mode="Markdown", reply_markup=buttons)
        logger.info(f"User {user.id} checked for live users. Found {len(live_users)} live. Points remaining: {user.points}")

    except Exception as e:
        logger.error(f"Error in check_live_handler for user {sender_id}: {e}", exc_info=True)
        session.rollback()
        raise


async def referrals_handler(session: Session, payload: dict):
    """Displays referral information and link."""
    try:
        callback_query = payload.get('callback_query', {})
        from_user = callback_query.get('from', {})
        sender_id = from_user.get('id')

        if not sender_id:
            logger.error("Could not determine sender_id from payload.")
            return

        user = session.query(TelegramUser).filter_by(id=sender_id).first()
        if not user:
            await send_user_feedback(sender_id, "❌ Please use /start first to register.")
            return

        # Count referrals
        referral_count = session.query(TelegramUser).filter_by(referred_by_id=user.id).count()
        
        referral_text = "┏━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        referral_text += "┃  🎁 *REFERRALS*  ┃\n"
        referral_text += "┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        
        referral_text += f"👥 *Total Referrals:* {referral_count}\n"
        referral_text += f"💰 *Points Earned:* {referral_count * 10}\n\n"
        
        referral_text += "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
        
        referral_text += "💡 *How it works:*\n\n"
        referral_text += "1️⃣ Share your link\n"
        referral_text += "2️⃣ Friend joins via link\n"
        referral_text += "3️⃣ You both get +10 points!\n\n"
        
        bot_username = os.environ.get('BOT_USERNAME', 'InstaLiveProBot')
        referral_link = f"https://t.me/{bot_username}?start={user.id}"
        
        referral_text += "🔗 *Your Referral Link:*\n"
        referral_text += f"`{referral_link}`\n\n"
        referral_text += "_(Tap to copy)_"
        
        helper = TelegramHelper()
        buttons = {
            "inline_keyboard": [
                [
                    {"text": "📤 Share Link", "url": f"https://t.me/share/url?url={referral_link}&text=Join me on IGLiveZBot!"}
                ],
                [
                    {"text": "⬅️ Back to Menu", "callback_data": "back"}
                ]
            ]
        }
        await helper.send_message(sender_id, referral_text, parse_mode="Markdown", reply_markup=buttons)

    except Exception as e:
        logger.error(f"Error in referrals_handler: {e}", exc_info=True)
        raise


async def help_handler(session: Session, payload: dict):
    """Displays help information."""
    try:
        callback_query = payload.get('callback_query', {})
        from_user = callback_query.get('from', {})
        sender_id = from_user.get('id')

        if not sender_id:
            return

        help_text = "┏━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        help_text += "┃  ℹ️ *HELP & INFO*  ┃\n"
        help_text += "┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        
        help_text += "🤖 *What is IGLiveZBot?*\n"
        help_text += "Track Instagram live streams in real-time!\n\n"
        
        help_text += "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
        
        help_text += "📋 *How to use:*\n\n"
        help_text += "🔴 *Check Live* - See who's streaming\n"
        help_text += "   Costs 1 point per check\n\n"
        
        help_text += "👤 *My Account* - View your stats\n"
        help_text += "   Check points & subscription\n\n"
        
        help_text += "🎁 *Referrals* - Earn bonus points\n"
        help_text += "   +10 points per friend\n\n"
        
        help_text += "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
        
        help_text += "💎 *Points System:*\n"
        help_text += "  • Start with 10 free points\n"
        help_text += "  • Resets daily at midnight UTC\n"
        help_text += "  • Earn more via referrals\n\n"
        
        help_text += "❓ *Need more help?*\n"
        help_text += "Contact support in our group!"
        
        helper = TelegramHelper()
        buttons = {
            "inline_keyboard": [
                [
                    {"text": "💬 Join Support Group", "url": REQUIRED_GROUP_URL}
                ],
                [
                    {"text": "⬅️ Back to Menu", "callback_data": "back"}
                ]
            ]
        }
        await helper.send_message(sender_id, help_text, parse_mode="Markdown", reply_markup=buttons)

    except Exception as e:
        logger.error(f"Error in help_handler: {e}", exc_info=True)
        raise


async def back_handler(session: Session, payload: dict):
    """Returns user to main menu."""
    try:
        callback_query = payload.get('callback_query', {})
        from_user = callback_query.get('from', {})
        sender_id = from_user.get('id')
        username = from_user.get('first_name', 'there')

        if not sender_id:
            return

        await send_main_menu(sender_id, username=username)

    except Exception as e:
        logger.error(f"Error in back_handler: {e}", exc_info=True)
        raise


# Keep other handlers (join_request_handler, etc.) from original file
async def join_request_handler(session: Session, payload: dict):
    """Handles chat join requests."""
    try:
        join_request = payload.get('chat_join_request', {})
        chat = join_request.get('chat', {})
        user = join_request.get('from', {})
        
        chat_id = chat.get('id')
        user_id = user.get('id')

        if not chat_id or not user_id:
            logger.error("Could not determine chat_id or user_id from join request payload.")
            return

        helper = TelegramHelper()
        await helper.approve_chat_join_request(chat_id, user_id)
        logger.info(f"Auto-approved join request for user {user_id} in chat {chat_id}")

    except Exception as e:
        logger.error(f"Error in join_request_handler: {e}", exc_info=True)
        raise
