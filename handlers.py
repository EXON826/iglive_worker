# worker/handlers_improved.py
# Improved UI/UX version with better formatting, emojis, and user experience

import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

from models import TelegramUser, ChatGroup
from telegram_helper import TelegramHelper
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


async def send_main_menu(user_id: int, prefix_message: str = "", username: str = None, lang: str = 'en', session: Session = None):
    """Send the main menu to a user with improved UI."""
    try:
        # Greeting personalization
        greeting = f"Hey {username}! 👋" if username else get_text('welcome_back', lang)
        
        menu_text = f"{prefix_message}{greeting}\n\n"
        menu_text += get_text('bot_title', lang) + "\n"
        menu_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Add quick stats if session provided
        if session:
            try:
                user = session.query(TelegramUser).filter_by(id=user_id).first()
                if user:
                    # Check if premium
                    now_utc = datetime.now(timezone.utc)
                    if user.subscription_end:
                        sub_end = user.subscription_end if user.subscription_end.tzinfo else user.subscription_end.replace(tzinfo=timezone.utc)
                        is_premium = sub_end > now_utc
                    else:
                        is_premium = False
                    
                    if is_premium:
                        menu_text += "💎 *Status:* Premium ✨\n"
                    else:
                        # Visual progress bar for points
                        points_bar = "█" * user.points + "░" * (3 - user.points)
                        menu_text += f"💰 *Points:* {user.points}/3 [{points_bar}]\n"
                    
                    # Get live count
                    live_count = session.execute(text("SELECT COUNT(*) FROM insta_links WHERE is_live = TRUE")).scalar()
                    menu_text += f"🔴 *Live Now:* {live_count} streams\n\n"
                    menu_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            except:
                pass
        
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
                    {"text": "⭐ Buy Premium", "callback_data": "buy"}
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
                points=3,
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
                    referrer.points += 5
                    session.commit()
                    
                    referrer_msg = f"🎊 *Referral Success!*\n\n"
                    referrer_msg += f"{username} just joined using your referral link!\n\n"
                    referrer_msg += "💰 *Reward:* +5 Points\n"
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
            user.points = 3
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

        await send_main_menu(user.id, prefix_message, username, user.language, session)

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

        # Fix timezone comparison
        now_utc = datetime.now(timezone.utc)
        if user.subscription_end:
            sub_end = user.subscription_end if user.subscription_end.tzinfo else user.subscription_end.replace(tzinfo=timezone.utc)
            is_unlimited = sub_end > now_utc
        else:
            is_unlimited = False
        
        # Count total checks (approximate from points used)
        referral_count = session.query(TelegramUser).filter_by(referred_by_id=user.id).count()
        
        # Create visual account card
        account_text = "👤 *YOUR ACCOUNT*\n"
        account_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        account_text += f"👤 *Name:* {user.first_name}\n"
        account_text += f"🆔 *Username:* @{user.username or 'Not set'}\n"
        account_text += f"🔢 *User ID:* `{user.id}`\n"
        account_text += f"📅 *Joined:* {user.last_seen.strftime('%b %d, %Y') if user.last_seen else 'Unknown'}\n"
        account_text += f"👥 *Referrals:* {referral_count} friends\n\n"
        
        if is_unlimited:
            days_left = (sub_end - now_utc).days
            account_text += "💎 *PREMIUM STATUS*\n"
            account_text += "━━━━━━━━━━━━━━━━━━━━\n"
            account_text += f"✅ Unlimited Checks\n"
            account_text += f"📅 Valid Until: {user.subscription_end.strftime('%b %d, %Y')}\n"
            account_text += f"⏳ Days Left: {days_left} days\n"
        else:
            points_bar = "█" * user.points + "░" * (3 - user.points)
            account_text += "💰 *FREE ACCOUNT*\n"
            account_text += "━━━━━━━━━━━━━━━━━━━━\n"
            account_text += f"💎 Points: *{user.points}/3* [{points_bar}]\n"
            account_text += f"🔄 Resets: Daily at midnight UTC\n\n"
            account_text += "❌ *What you're missing:*\n"
            account_text += "  • Unlimited checks\n"
            account_text += "  • No daily limits\n"
            account_text += "  • Priority features\n"
        
        account_text += "\n💡 *Tip:* Refer friends to earn bonus points!"
        
        buttons = {
            "inline_keyboard": [
                [
                    {"text": "⭐ Buy Points/Premium", "callback_data": "buy"}
                ],
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
        now_utc = datetime.now(timezone.utc)
        if user.subscription_end:
            sub_end = user.subscription_end if user.subscription_end.tzinfo else user.subscription_end.replace(tzinfo=timezone.utc)
            is_unlimited = sub_end > now_utc
        else:
            is_unlimited = False
        if not is_unlimited and page == 1:
            if user.points > 0:
                user.points -= 1
                session.commit()
            else:
                no_points_msg = "😢 *No Points Left!*\n\n"
                no_points_msg += "You're missing live streams right now!\n\n"
                no_points_msg += "🌟 *UPGRADE TO PREMIUM:*\n"
                no_points_msg += "  ✅ Unlimited checks 24/7\n"
                no_points_msg += "  ⚡ Never miss a stream\n"
                no_points_msg += "  💎 Only ⭐150 for 7 days\n\n"
                no_points_msg += "🔄 *Or wait:* Points reset at midnight UTC\n"
                no_points_msg += "🎁 *Or refer:* Get +5 points per friend\n"
                
                buttons = {
                    "inline_keyboard": [
                        [{"text": "🌟 Upgrade Now", "callback_data": "buy"}],
                        [{"text": "🎁 Get Referral Link", "callback_data": "referrals"}],
                        [{"text": "⬅️ Back", "callback_data": "back"}]
                    ]
                }
                
                logger.info(f"User {user.id} has no points left.")
                await helper.send_message(sender_id, no_points_msg, parse_mode="Markdown", reply_markup=buttons)
                return
        
        # Get live users from database
        try:
            query = text("""
                SELECT username, last_live_at, total_lives, link
                FROM insta_links
                WHERE is_live = TRUE
                ORDER BY last_live_at DESC
            """)
            result = session.execute(query).fetchall()
            
            live_users = []
            for row in result:
                live_users.append({
                    'username': row[0],
                    'last_live_at': row[1],
                    'total_lives': row[2],
                    'link': row[3]
                })
        except Exception as e:
            logger.error(f"Error fetching live users: {e}")
            live_users = []
        
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
            
            for idx, user_data in enumerate(page_users, 1):
                username = user_data['username']
                link = user_data.get('link', f"https://instagram.com/{username.lstrip('@')}")
                total_lives = user_data.get('total_lives', 0)
                
                # Add metadata
                live_message += f"{idx}. 🔴 *[{username}]({link})*\n"
                if total_lives > 0:
                    live_message += f"   📊 Total lives: {total_lives}\n"
        else:
            live_message = "🔴 *LIVE NOW*\n"
            live_message += "━━━━━━━━━━━━━━━━━━━━\n\n"
            live_message += "😴 *No one is live right now.*\n\n"
            live_message += "💡 *What you can do:*\n"
            live_message += "  • Check back in a few minutes\n"
            live_message += "  • Upgrade for instant notifications\n"
            live_message += "  • Invite friends for bonus points\n"
        
        # Calculate time until reset
        now_utc = datetime.now(timezone.utc)
        tomorrow_utc = (now_utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        time_until_reset = tomorrow_utc - now_utc
        hours = int(time_until_reset.total_seconds() // 3600)
        minutes = int((time_until_reset.total_seconds() % 3600) // 60)
        
        # Add points/subscription info
        live_message += "\n━━━━━━━━━━━━━━━━━━━━\n"
        if is_unlimited:
            live_message += f"💎 *Status:* Premium (Unlimited)\n"
        else:
            live_message += f"💰 *Points Left:* {user.points}/3\n"
            live_message += f"⏰ *Reset in:* {hours}h {minutes}m\n"
        
        live_message += f"🔄 *Updated:* {datetime.now(timezone.utc).strftime('%I:%M %p UTC')}"
        
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
        
        if not is_unlimited:
            button_rows.append([{"text": "🌟 Upgrade to Unlimited", "callback_data": "buy"}])
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
        referral_text += f"💰 *Points Earned:* {referral_count * 5}\n\n"
        
        # Progress to free premium
        if referral_count < 30:
            progress = min(referral_count, 30)
            progress_bar = "█" * (progress // 3) + "░" * (10 - progress // 3)
            referral_text += f"🎯 *Progress to Free Premium:*\n"
            referral_text += f"   [{progress_bar}] {referral_count}/30\n\n"
        else:
            referral_text += "🏆 *Achievement Unlocked!*\n"
            referral_text += "   You've earned free premium! 🎉\n\n"
        
        referral_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        referral_text += "💡 *How it works:*\n\n"
        referral_text += "1️⃣ Share your link\n"
        referral_text += "2️⃣ Friend joins via link\n"
        referral_text += "3️⃣ You both get +5 points!\n"
        referral_text += "🎁 30 referrals = Free 7-day Premium!\n\n"
        
        bot_username = os.environ.get('BOT_USERNAME', 'InstaLiveProBot')
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
        user = session.query(TelegramUser).filter_by(id=sender_id).first()
        lang = user.language if user else 'en'

        help_text = "ℹ️ *HELP & INFO*\n"
        help_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        help_text += "🤖 *What is IGLiveZBot?*\n"
        help_text += "Track Instagram live streams in real-time!\n\n"
        
        help_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        help_text += "📋 *How to use:*\n\n"
        help_text += "🔴 *Check Live* - See who's streaming\n"
        help_text += "   Costs 1 point per check\n\n"
        
        help_text += "👤 *My Account* - View your stats\n"
        help_text += "   Check points & subscription\n\n"
        
        help_text += "🎁 *Referrals* - Earn bonus points\n"
        help_text += "   +10 points per friend\n\n"
        
        help_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        help_text += "💎 *Points System:*\n"
        help_text += "  • Start with 3 free points\n"
        help_text += "  • Resets daily at midnight UTC\n"
        help_text += "  • Earn +5 points per referral\n"
        help_text += "  • 1 point = 1 live check\n\n"
        
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

        if not sender_id:
            return

        user = session.query(TelegramUser).filter_by(id=sender_id).first()
        lang = user.language if user else 'en'
        await send_main_menu(sender_id, username=username, lang=lang, session=session)

    except Exception as e:
        logger.error(f"Error in back_handler: {e}", exc_info=True)
        raise


async def settings_handler(session: Session, payload: dict):
    """Displays settings menu."""
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

        settings_text = "⚙️ *SETTINGS*\n"
        settings_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        settings_text += f"🌍 *Current Language:* {LANGUAGE_NAMES.get(user.language, 'English')}\n\n"
        settings_text += "Choose an option below:"

        buttons = {
            "inline_keyboard": [
                [
                    {"text": "🌍 Change Language", "callback_data": "lang:select"}
                ],
                [
                    {"text": "⬅️ Back to Menu", "callback_data": "back"}
                ]
            ]
        }
        await helper.edit_message_text(chat_id, message_id, settings_text, parse_mode="Markdown", reply_markup=buttons)

    except Exception as e:
        logger.error(f"Error in settings_handler: {e}", exc_info=True)
        raise


async def set_initial_language_handler(session: Session, payload: dict):
    """Handles initial language selection for new users."""
    try:
        callback_query = payload.get('callback_query', {})
        from_user = callback_query.get('from', {})
        sender_id = from_user.get('id')
        callback_data = callback_query.get('data', '')
        username = from_user.get('first_name', 'there')

        if not sender_id:
            return

        # Extract language code from callback_data (format: "setlang:en")
        lang_code = callback_data.split(':')[1] if ':' in callback_data else 'en'

        user = session.query(TelegramUser).filter_by(id=sender_id).first()
        if user:
            user.language = lang_code
            session.commit()
            logger.info(f"User {user.id} set initial language to {lang_code}")

        # Send main menu with selected language
        prefix_message = get_text('language_set', lang_code) + "\n\n"
        await send_main_menu(sender_id, prefix_message, username, lang_code)

    except Exception as e:
        logger.error(f"Error in set_initial_language_handler: {e}", exc_info=True)
        raise


async def change_language_handler(session: Session, payload: dict):
    """Handles language change from settings."""
    try:
        callback_query = payload.get('callback_query', {})
        from_user = callback_query.get('from', {})
        sender_id = from_user.get('id')
        callback_data = callback_query.get('data', '')
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

        # If callback is "lang:select", show language selection menu
        if callback_data == "lang:select":
            lang_text = "🌍 *SELECT LANGUAGE*\n"
            lang_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            lang_text += "Choose your preferred language:"

            # Create language selection buttons (2 per row)
            lang_buttons = []
            languages = list(LANGUAGE_NAMES.items())
            for i in range(0, len(languages), 2):
                row = []
                for j in range(2):
                    if i + j < len(languages):
                        lang_code, lang_name = languages[i + j]
                        display_name = f"✓ {lang_name}" if lang_code == user.language else lang_name
                        row.append({"text": display_name, "callback_data": f"lang:{lang_code}"})
                lang_buttons.append(row)
            
            lang_buttons.append([{"text": "⬅️ Back", "callback_data": "settings"}])
            buttons = {"inline_keyboard": lang_buttons}
            
            await helper.edit_message_text(chat_id, message_id, lang_text, parse_mode="Markdown", reply_markup=buttons)
        else:
            # Extract language code and update
            lang_code = callback_data.split(':')[1] if ':' in callback_data else user.language
            user.language = lang_code
            session.commit()
            logger.info(f"User {user.id} changed language to {lang_code}")

            # Show confirmation and return to settings
            confirm_text = get_text('language_changed', lang_code) + "\n\n"
            confirm_text += "⚙️ *SETTINGS*\n"
            confirm_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            confirm_text += f"🌍 *Current Language:* {LANGUAGE_NAMES.get(lang_code, 'English')}\n\n"
            confirm_text += "Choose an option below:"

            buttons = {
                "inline_keyboard": [
                    [
                        {"text": get_text('change_language', lang_code), "callback_data": "lang:select"}
                    ],
                    [
                        {"text": get_text('back', lang_code), "callback_data": "back"}
                    ]
                ]
            }
            await helper.edit_message_text(chat_id, message_id, confirm_text, parse_mode="Markdown", reply_markup=buttons)

    except Exception as e:
        logger.error(f"Error in change_language_handler: {e}", exc_info=True)
        raise


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


async def broadcast_message_handler(session: Session, payload: dict):
    """Handles broadcasting messages to all users."""
    try:
        message_text = payload.get('message', '')
        if not message_text:
            logger.warning("No message text provided for broadcast.")
            return

        # Get all users
        users = session.query(TelegramUser).all()
        helper = TelegramHelper()
        
        success_count = 0
        fail_count = 0
        
        for user in users:
            try:
                await helper.send_message(user.id, message_text, parse_mode="Markdown")
                success_count += 1
                await asyncio.sleep(0.05)  # Rate limiting
            except Exception as e:
                logger.error(f"Failed to send broadcast to user {user.id}: {e}")
                fail_count += 1
        
        logger.info(f"Broadcast completed. Success: {success_count}, Failed: {fail_count}")

    except Exception as e:
        logger.error(f"Error in broadcast_message_handler: {e}", exc_info=True)
        raise


async def init_handler(session: Session, payload: dict):
    """Handles /init command (placeholder for future use)."""
    try:
        message = payload.get('message', {})
        from_user = message.get('from', {})
        sender_id = from_user.get('id')
        
        if not sender_id:
            return

        await send_user_feedback(sender_id, "ℹ️ This command is reserved for future features.")
        logger.info(f"User {sender_id} used /init command")

    except Exception as e:
        logger.error(f"Error in init_handler: {e}", exc_info=True)
        raise


async def activate_handler(session: Session, payload: dict):
    """Handles /activate command (placeholder for future use)."""
    try:
        message = payload.get('message', {})
        from_user = message.get('from', {})
        sender_id = from_user.get('id')
        
        if not sender_id:
            return

        await send_user_feedback(sender_id, "ℹ️ This command is reserved for future features.")
        logger.info(f"User {sender_id} used /activate command")

    except Exception as e:
        logger.error(f"Error in activate_handler: {e}", exc_info=True)
        raise
