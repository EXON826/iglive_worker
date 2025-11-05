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
from translations import get_text, detect_language, LANGUAGE_NAMES

logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
BOT_API_ID = os.environ.get('BOT_API_ID')
BOT_API_HASH = os.environ.get('BOT_API_HASH')

REQUIRED_GROUP_URL = "https://t.me/+FBDgBcLD1C5jN2Jk"
REQUIRED_GROUP_ID = -1002891494486

# Feature flag: Set to False to disable group membership requirement
REQUIRE_GROUP_MEMBERSHIP = False


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


async def send_main_menu(user_id: int, prefix_message: str = "", username: str = None, lang: str = 'en'):
    """Send the main menu to a user with improved UI."""
    try:
        # Greeting personalization
        greeting = f"Hey {username}! 👋" if username else get_text('welcome_back', lang)
        
        menu_text = f"{prefix_message}{greeting}\n\n"
        menu_text += get_text('bot_title', lang) + "\n"
        menu_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        menu_text += get_text('track_ig_live', lang) + "\n"
        menu_text += f"     {get_text('track_ig_desc', lang)}\n\n"
        menu_text += get_text('smart_points', lang) + "\n"
        menu_text += f"     {get_text('smart_points_desc', lang)}\n\n"
        menu_text += get_text('refer_earn', lang) + "\n"
        menu_text += f"     {get_text('refer_earn_desc', lang)}\n\n"
        menu_text += get_text('choose_option', lang)

        buttons = {
            "inline_keyboard": [
                [
                    {"text": get_text('check_live', lang), "callback_data": "check_live"}
                ],
                [
                    {"text": get_text('my_account', lang), "callback_data": "my_account"},
                    {"text": get_text('referrals', lang), "callback_data": "referrals"}
                ],
                [
                    {"text": get_text('help', lang), "callback_data": "help"},
                    {"text": get_text('settings', lang), "callback_data": "settings"}
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
        if REQUIRE_GROUP_MEMBERSHIP:
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
            # New user registration - show language selection first
            referred_by_id = None
            text = message.get('text', '')
            if text and len(text.split()) > 1:
                try:
                    referred_by_id = int(text.split()[1])
                    if referred_by_id == sender_id:
                        referred_by_id = None
                except (ValueError, IndexError):
                    referred_by_id = None

            # Detect user's language from Telegram as default
            user_lang = detect_language(from_user.get('language_code', 'en'))

            # Create user with temporary language (will be confirmed by user)
            user = TelegramUser(
                id=sender_id,
                username=from_user.get('username'),
                first_name=from_user.get('first_name'),
                points=10,
                last_seen=datetime.now(timezone.utc),
                referred_by_id=referred_by_id,
                language=user_lang
            )
            session.add(user)
            session.commit()
            
            logger.info(f"New user created: {user.id} (@{user.username}) with detected language: {user_lang}")

            # Award referral points
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

            # Show language selection menu for new users
            welcome_text = "🎉 *Welcome to IGLiveZBot!*\n\n"
            welcome_text += f"Hey {username}! Great to have you here.\n\n"
            welcome_text += "🌍 *Please select your preferred language:*"
            
            # Create language selection buttons (2 per row)
            lang_buttons = []
            languages = list(LANGUAGE_NAMES.items())
            for i in range(0, len(languages), 2):
                row = []
                for j in range(2):
                    if i + j < len(languages):
                        lang_code, lang_name = languages[i + j]
                        # Highlight detected language
                        display_name = f"✓ {lang_name}" if lang_code == user_lang else lang_name
                        row.append({"text": display_name, "callback_data": f"setlang:{lang_code}"})
                lang_buttons.append(row)
            
            buttons = {"inline_keyboard": lang_buttons}
            
            await helper.send_message(sender_id, welcome_text, parse_mode="Markdown", reply_markup=buttons)
            logger.info(f"Sent language selection to new user {user.id}")
            return  # Don't show main menu yet

        elif is_new_day_for_user(user):
            # Daily reset
            user.points = 10
            user.last_seen = datetime.now(timezone.utc)
            session.commit()
            
            prefix_message = get_text('good_morning', user.language) + "\n\n"
            prefix_message += get_text('daily_reset', user.language) + "\n\n"
            prefix_message += get_text('daily_bonus', user.language) + "\n\n"
            
            logger.info(f"Reset daily points for user {user.id}")
        else:
            # Returning user
            user.last_seen = datetime.now(timezone.utc)
            session.commit()

        await send_main_menu(user.id, prefix_message, username, user.language)

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
        message = callback_query.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        message_id = message.get('message_id')

        if not sender_id:
            logger.error("Could not determine sender_id from payload.")
            return

        helper = TelegramHelper()

        user = session.query(TelegramUser).filter_by(id=sender_id).first()
        if not user:
            logger.warning(f"User {sender_id} not found for my_account.")
            await send_user_feedback(sender_id, "❌ Please use /start first to register.")
            return

        is_unlimited = user.subscription_end and user.subscription_end > datetime.now(timezone.utc)
        
        # Create visual account card
        account_text = "👤 *YOUR ACCOUNT*\n"
        account_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        account_text += f"👤 *Name:* {user.first_name}\n"
        account_text += f"🆔 *Username:* @{user.username or 'Not set'}\n"
        account_text += f"🔢 *User ID:* `{user.id}`\n"
        account_text += f"📅 *Joined:* {user.last_seen.strftime('%b %d, %Y') if user.last_seen else 'Unknown'}\n\n"
        
        if is_unlimited:
            account_text += "💎 *PREMIUM STATUS*\n"
            account_text += "━━━━━━━━━━━━━━━━━━━━\n"
            account_text += f"✅ Unlimited Checks\n"
            account_text += f"📅 Valid Until: {user.subscription_end.strftime('%b %d, %Y')}\n"
        else:
            account_text += "💰 *POINTS BALANCE*\n"
            account_text += "━━━━━━━━━━━━━━━━━━━━\n"
            account_text += f"💎 Current: *{user.points} points*\n"
            account_text += f"🔄 Resets: Daily at midnight UTC\n"
            account_text += f"✨ Cost: 1 point per check\n"
        
        account_text += "\n💡 *Tip:* Refer friends to earn bonus points!"
        
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
        
        # Edit the existing message instead of sending a new one
        await helper.edit_message_text(chat_id, message_id, account_text, parse_mode="Markdown", reply_markup=buttons)
        logger.info(f"Edited message with account details for user {user.id}")

    except Exception as e:
        logger.error(f"Error in my_account_handler for user {sender_id}: {e}", exc_info=True)
        raise


async def check_live_handler(session: Session, payload: dict):
    """Displays currently live Instagram users with pagination."""
    try:
        callback_query = payload.get('callback_query', {})
        from_user = callback_query.get('from', {})
        sender_id = from_user.get('id')
        message = callback_query.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        message_id = message.get('message_id')

        if not sender_id:
            logger.error("Could not determine sender_id from payload.")
            return

        helper = TelegramHelper()

        # Parse page number from callback_data (e.g., "check_live:2")
        callback_data = callback_query.get('data', 'check_live')
        page = 1
        if ':' in callback_data:
            try:
                page = int(callback_data.split(':')[1])
            except (ValueError, IndexError):
                page = 1

        user = session.query(TelegramUser).filter_by(id=sender_id).first()
        if not user:
            logger.warning(f"User {sender_id} not found for check_live.")
            await send_user_feedback(sender_id, "❌ Please use /start first to register.")
            return

        # Check points/subscription (only deduct on first page)
        is_unlimited = user.subscription_end and user.subscription_end > datetime.now(timezone.utc)
        if not is_unlimited and page == 1:
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
        
        # Pagination setup
        PER_PAGE = 10
        total_users = len(live_users)
        total_pages = max(1, (total_users + PER_PAGE - 1) // PER_PAGE)
        page = max(1, min(page, total_pages))  # Clamp page to valid range
        
        start_idx = (page - 1) * PER_PAGE
        end_idx = start_idx + PER_PAGE
        page_users = live_users[start_idx:end_idx]
        
        # Format the live users message
        if live_users:
            live_message = "🔴 *LIVE NOW*\n"
            live_message += "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            if total_pages > 1:
                live_message += f"📄 Page {page}/{total_pages} • {total_users} total streams\n\n"
            else:
                live_message += f"Found *{total_users}* live stream{'s' if total_users != 1 else ''}!\n\n"
            
            for user_data in page_users:
                username = user_data['username']
                link = user_data.get('link', f"https://instagram.com/{username.lstrip('@')}")
                
                live_message += f"▸ 🔴 *[{username}]({link})*\n"
        else:
            live_message = "🔴 *LIVE NOW*\n"
            live_message += "━━━━━━━━━━━━━━━━━━━━\n\n"
            live_message += "😴 No one is live right now.\n\n"
            live_message += "💡 Live streams are tracked in real-time.\n"
            live_message += "   Check back in a few minutes!\n"
        
        # Add points/subscription info
        live_message += "\n━━━━━━━━━━━━━━━━━━━━\n"
        if is_unlimited:
            live_message += f"💎 *Status:* Premium (Unlimited)\n"
        else:
            live_message += f"💰 *Points Left:* {user.points}\n"
        
        live_message += f"⏰ *Updated:* {datetime.now(timezone.utc).strftime('%I:%M %p UTC')}"
        
        # Build pagination buttons
        button_rows = []
        
        if total_pages > 1:
            nav_buttons = []
            if page > 1:
                nav_buttons.append({"text": "⬅️ Previous", "callback_data": f"check_live:{page-1}"})
            if page < total_pages:
                nav_buttons.append({"text": "Next ➡️", "callback_data": f"check_live:{page+1}"})
            if nav_buttons:
                button_rows.append(nav_buttons)
        
        button_rows.append([{"text": "🔄 Refresh", "callback_data": "check_live"}])
        button_rows.append([{"text": "⬅️ Back to Menu", "callback_data": "back"}])
        
        buttons = {"inline_keyboard": button_rows}
        
        # Edit the existing message instead of sending a new one
        await helper.edit_message_text(chat_id, message_id, live_message, parse_mode="Markdown", reply_markup=buttons)
        logger.info(f"User {user.id} checked live users page {page}/{total_pages}. Total: {total_users} live. Points: {user.points}")

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
        message = callback_query.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        message_id = message.get('message_id')

        if not sender_id:
            logger.error("Could not determine sender_id from payload.")
            return

        helper = TelegramHelper()

        user = session.query(TelegramUser).filter_by(id=sender_id).first()
        if not user:
            await send_user_feedback(sender_id, "❌ Please use /start first to register.")
            return

        # Count referrals
        referral_count = session.query(TelegramUser).filter_by(referred_by_id=user.id).count()
        
        referral_text = "🎁 *REFERRALS*\n"
        referral_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        referral_text += f"👥 *Total Referrals:* {referral_count}\n"
        referral_text += f"💰 *Points Earned:* {referral_count * 10}\n\n"
        
        referral_text += "💡 *How it works:*\n"
        referral_text += "━━━━━━━━━━━━━━━━━━━━\n"
        referral_text += "1️⃣ Share your link\n"
        referral_text += "2️⃣ Friend joins via link\n"
        referral_text += "3️⃣ You both get +10 points!\n\n"
        
        bot_username = os.environ.get('BOT_USERNAME', 'IGLiveZBot')
        referral_link = f"https://t.me/{bot_username}?start={user.id}"
        
        referral_text += "🔗 *Your Referral Link:*\n"
        referral_text += f"`{referral_link}`\n\n"
        referral_text += "_(Tap to copy)_"
        
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
        
        # Edit the existing message instead of sending a new one
        await helper.edit_message_text(chat_id, message_id, referral_text, parse_mode="Markdown", reply_markup=buttons)

    except Exception as e:
        logger.error(f"Error in referrals_handler: {e}", exc_info=True)
        raise


async def help_handler(session: Session, payload: dict):
    """Displays help information."""
    try:
        callback_query = payload.get('callback_query', {})
        from_user = callback_query.get('from', {})
        sender_id = from_user.get('id')
        message = callback_query.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        message_id = message.get('message_id')

        if not sender_id:
            return

        helper = TelegramHelper()

        help_text = "ℹ️ *HELP & INFO*\n"
        help_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        help_text += "🤖 *What is IGLiveZBot?*\n"
        help_text += "Track Instagram live streams in real-time!\n\n"
        
        help_text += "📋 *How to use:*\n"
        help_text += "━━━━━━━━━━━━━━━━━━━━\n"
        help_text += "🔴 *Check Live* - See who's streaming\n"
        help_text += "     Costs 1 point per check\n\n"
        
        help_text += "👤 *My Account* - View your stats\n"
        help_text += "     Check points & subscription\n\n"
        
        help_text += "🎁 *Referrals* - Earn bonus points\n"
        help_text += "     +10 points per friend\n\n"
        
        help_text += "💎 *Points System:*\n"
        help_text += "━━━━━━━━━━━━━━━━━━━━\n"
        help_text += "  • Start with 10 free points\n"
        help_text += "  • Resets daily at midnight UTC\n"
        help_text += "  • Earn more via referrals\n\n"
        
        help_text += "❓ *Need more help?*\n"
        help_text += "Contact support in our group!"
        
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
        
        # Edit the existing message instead of sending a new one
        await helper.edit_message_text(chat_id, message_id, help_text, parse_mode="Markdown", reply_markup=buttons)

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
        message = callback_query.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        message_id = message.get('message_id')

        if not sender_id:
            return

        helper = TelegramHelper()
        
        # Build main menu text
        greeting = f"Hey {username}! 👋" if username else "Welcome back! 👋"
        
        menu_text = f"{greeting}\n\n"
        menu_text += "⭐️ *IGLiveZBot* ⭐️\n"
        menu_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        menu_text += "🔴 *Track Instagram Live Streams*\n"
        menu_text += "     See who's live in real-time\n\n"
        menu_text += "💎 *Smart Points System*\n"
        menu_text += "     Get 10 free points daily\n\n"
        menu_text += "🎁 *Refer & Earn*\n"
        menu_text += "     10 bonus points per referral\n\n"
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
        
        # Edit the existing message instead of sending a new one
        await helper.edit_message_text(chat_id, message_id, menu_text, parse_mode="Markdown", reply_markup=buttons)

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

        # Check if the user is an admin in the group
        helper = TelegramHelper()
        is_admin = await helper.is_user_admin(chat_id, user_id)
        if not is_admin:
            await helper.send_message(chat_id, "❌ You must be an admin of this group to use the /init command.")
            logger.warning(f"User {user_id} tried to /init in {chat_id} but is not an admin.")
            return

        # Check if the bot itself is an admin
        bot_is_admin = await helper.is_bot_admin(chat_id)
        if not bot_is_admin:
            await helper.send_message(chat_id, "⚠️ This bot must be an administrator in this group to function correctly.")
            logger.warning(f"Bot is not an admin in chat {chat_id}. Cannot complete /init.")
            return

        # Register the group and admin
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
        
        success_msg = "✅ *Group Registered Successfully!*\n\n"
        success_msg += f"📱 *Group:* {chat_title}\n"
        success_msg += f"👤 *Admin:* {from_user.get('first_name')}\n\n"
        success_msg += "🎉 This group is now active for broadcasts!"
        
        logger.info(f"Group {chat_id} ('{chat_title}') initialized/updated by admin {user_id}.")
        await helper.send_message(chat_id, success_msg, parse_mode="Markdown")

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

        # Find the group in the database
        group = session.query(ChatGroup).filter_by(chat_id=str(chat_id), is_active=True).first()
        if not group:
            await send_user_feedback(user_id, "❌ This group is not registered. Please use /init in the group first.")
            return

        # Check if the user is the registered admin of this group
        if group.admin_user_id != user_id:
            await send_user_feedback(user_id, "❌ You are not the registered admin for this group.")
            return
            
        # Grant unlimited points to the user
        user = session.query(TelegramUser).filter_by(id=user_id).first()
        if not user:
            logger.warning(f"User {user_id} used /activate but was not in the users table. Creating new entry.")
            user = TelegramUser(id=user_id, username=from_user.get('username'), first_name=from_user.get('first_name'))
            session.add(user)

        # Set subscription_end to a far-future date to represent "unlimited"
        user.subscription_end = datetime(2099, 12, 31, tzinfo=timezone.utc)
        session.commit()

        premium_msg = "🎊 *PREMIUM ACTIVATED!*\n\n"
        premium_msg += "💎 You now have *UNLIMITED* access!\n\n"
        premium_msg += "✨ *Benefits:*\n"
        premium_msg += "  • Unlimited live checks\n"
        premium_msg += "  • No daily point limits\n"
        premium_msg += "  • Priority support\n\n"
        premium_msg += "🔥 Enjoy your premium experience!"

        logger.info(f"User {user_id} has been granted unlimited points via group {chat_id}.")
        await send_user_feedback(user_id, premium_msg)

    except Exception as e:
        logger.error(f"Error in activate_handler for user {user_id}: {e}", exc_info=True)
        session.rollback()
        raise


async def broadcast_message_handler(session: Session, payload: dict):
    """
    Handles a broadcast_message job, sending a message to all active groups.
    """
    try:
        message_text = payload.get('text')
        if not message_text:
            logger.error("Broadcast job is missing 'text' in payload.")
            return

        # Fetch all active groups
        active_groups = session.query(ChatGroup).filter_by(is_active=True).all()
        
        if not active_groups:
            logger.info("No active groups to broadcast to.")
            return

        helper = TelegramHelper()
        success_count = 0
        fail_count = 0
        
        for group in active_groups:
            try:
                chat_id = int(group.chat_id)
                await helper.send_message(chat_id, message_text, parse_mode="Markdown")
                logger.info(f"Broadcasted message to group {chat_id}.")
                success_count += 1
                # Rate limiting
                await asyncio.sleep(1)
            except ValueError:
                logger.warning(f"Could not convert chat_id '{group.chat_id}' to int. Skipping.")
                fail_count += 1
            except Exception as e:
                logger.error(f"Failed to broadcast to group {group.chat_id}: {e}")
                fail_count += 1

        logger.info(f"Broadcast complete: {success_count} successful, {fail_count} failed")

    except Exception as e:
        logger.error(f"Error in broadcast_message_handler: {e}", exc_info=True)


async def settings_handler(session: Session, payload: dict):
    """Display settings menu with language selection."""
    try:
        callback_query = payload.get('callback_query', {})
        from_user = callback_query.get('from', {})
        sender_id = from_user.get('id')
        message = callback_query.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        message_id = message.get('message_id')

        if not sender_id:
            return

        helper = TelegramHelper()
        
        user = session.query(TelegramUser).filter_by(id=sender_id).first()
        if not user:
            await send_user_feedback(sender_id, "❌ Please use /start first to register.")
            return

        lang = user.language
        
        settings_text = get_text('settings_title', lang) + "\n"
        settings_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        settings_text += get_text('current_language', lang, language=LANGUAGE_NAMES.get(lang, lang)) + "\n\n"
        settings_text += get_text('select_language', lang)
        
        # Create language selection buttons (2 per row)
        lang_buttons = []
        languages = list(LANGUAGE_NAMES.items())
        for i in range(0, len(languages), 2):
            row = []
            for j in range(2):
                if i + j < len(languages):
                    lang_code, lang_name = languages[i + j]
                    # Add checkmark to current language
                    display_name = f"✓ {lang_name}" if lang_code == lang else lang_name
                    row.append({"text": display_name, "callback_data": f"lang:{lang_code}"})
            lang_buttons.append(row)
        
        lang_buttons.append([{"text": get_text('back_to_menu', lang), "callback_data": "back"}])
        
        buttons = {"inline_keyboard": lang_buttons}
        
        await helper.edit_message_text(chat_id, message_id, settings_text, parse_mode="Markdown", reply_markup=buttons)
        logger.info(f"Displayed settings for user {user.id}")

    except Exception as e:
        logger.error(f"Error in settings_handler: {e}", exc_info=True)
        raise


async def set_initial_language_handler(session: Session, payload: dict):
    """Handle initial language selection for new users."""
    try:
        callback_query = payload.get('callback_query', {})
        from_user = callback_query.get('from', {})
        sender_id = from_user.get('id')
        username = from_user.get('first_name', 'there')
        callback_data = callback_query.get('data', '')

        if not sender_id or not callback_data.startswith('setlang:'):
            return

        # Extract language code from callback_data (e.g., "setlang:es" -> "es")
        selected_lang = callback_data.split(':')[1]
        
        if selected_lang not in LANGUAGE_NAMES:
            logger.warning(f"Invalid language code: {selected_lang}")
            return

        user = session.query(TelegramUser).filter_by(id=sender_id).first()
        if not user:
            await send_user_feedback(sender_id, "❌ Please use /start first to register.")
            return

        # Update user's language
        user.language = selected_lang
        session.commit()
        
        logger.info(f"User {user.id} set initial language to {selected_lang}")
        
        # Show welcome message with bonuses in selected language
        prefix_message = get_text('welcome', selected_lang) + "\n\n"
        prefix_message += f"Hey {username}! Great to have you here.\n\n"
        prefix_message += get_text('starter_bonus', selected_lang) + "\n"
        if user.referred_by_id:
            prefix_message += get_text('referral_bonus', selected_lang) + "\n"
        prefix_message += "\n"
        
        # Show main menu
        await send_main_menu(user.id, prefix_message, username, selected_lang)

    except Exception as e:
        logger.error(f"Error in set_initial_language_handler: {e}", exc_info=True)
        session.rollback()
        raise


async def change_language_handler(session: Session, payload: dict):
    """Change user's language preference from settings."""
    try:
        callback_query = payload.get('callback_query', {})
        from_user = callback_query.get('from', {})
        sender_id = from_user.get('id')
        username = from_user.get('first_name', 'there')
        message = callback_query.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        message_id = message.get('message_id')
        callback_data = callback_query.get('data', '')

        if not sender_id or not callback_data.startswith('lang:'):
            return

        # Extract language code from callback_data (e.g., "lang:es" -> "es")
        new_lang = callback_data.split(':')[1]
        
        if new_lang not in LANGUAGE_NAMES:
            logger.warning(f"Invalid language code: {new_lang}")
            return

        helper = TelegramHelper()
        
        user = session.query(TelegramUser).filter_by(id=sender_id).first()
        if not user:
            await send_user_feedback(sender_id, "❌ Please use /start first to register.")
            return

        # Update user's language
        old_lang = user.language
        user.language = new_lang
        session.commit()
        
        logger.info(f"User {user.id} changed language from {old_lang} to {new_lang}")
        
        # Show confirmation and return to main menu
        confirmation = get_text('language_changed', new_lang, language=LANGUAGE_NAMES[new_lang]) + "\n\n"
        
        await send_main_menu(user.id, confirmation, username, new_lang)

    except Exception as e:
        logger.error(f"Error in change_language_handler: {e}", exc_info=True)
        session.rollback()
        raise
