# worker/handlers_improved_ui.py
# Enhanced UI/UX version with animated progress bars, card-style formatting, and loading states

import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

from models import (
    TelegramUser, InstaLink, ChatGroup, UserActivity, 
    Job, Referral, PointsTransaction, StarPayment,
    LiveNotificationMessage, SystemSettings, EphemeralMessage
)
from telegram_helper import TelegramHelper
from translations import get_text, detect_language, LANGUAGE_NAMES
from smart_notifications import send_referral_milestone_notification
from rate_limiter import rate_limiter
from config import (
    BOT_USERNAME, BOT_TOKEN, BOT_API_ID, BOT_API_HASH,
    REQUIRED_GROUP_URL, REQUIRED_GROUP_ID, REQUIRE_GROUP_MEMBERSHIP,
    LIVE_STREAMS_PER_PAGE, PREMIUM_VALIDITY_DAYS,
    DEFAULT_DAILY_POINTS, REFERRAL_BONUS_POINTS, FREE_PREMIUM_REFERRAL_THRESHOLD,
    ADMIN_IDS, AUTO_BROADCAST_THRESHOLD, AUTO_BROADCAST_COOLDOWN_HOURS
)

logger = logging.getLogger(__name__)


def md_escape(text: str) -> str:
    """Escape Telegram Markdown (v1) special chars in dynamic text."""
    if not text:
        return ""
    return (text
        .replace('\\', '\\\\')
        .replace('_', '\\_')
        .replace('*', '\\*')
        .replace('[', '\\[')
        .replace(']', '\\]')
        .replace('(', '\\(')
        .replace(')', '\\)')
        .replace('`', '\\`')
    )


def md_link(title: str, url: str) -> str:
    """Safe clickable link for Markdown."""
    return f"[{md_escape(title)}]({url})"


def get_animated_progress_bar(current: int, total: int, length: int = 10) -> str:
    """Create animated progress bar with ▰▱ characters."""
    filled = int((current / total) * length) if total > 0 else 0
    return "▰" * filled + "▱" * (length - filled)


def get_relative_time(dt: datetime) -> str:
    """Convert datetime to relative time string."""
    if not dt:
        return "Unknown"
    
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    diff = now - dt
    seconds = int(diff.total_seconds())
    
    if seconds < 60:
        return "Just now"
    elif seconds < 3600:
        return f"{seconds // 60}m ago"
    elif seconds < 86400:
        return f"{seconds // 3600}h ago"
    else:
        return f"{seconds // 86400}d ago"


def create_stream_card(username: str, link: str, total_lives: int, last_live: datetime, index: int) -> str:
    """Create card-style formatting for live stream."""
    card = (
        f"┌────────────────────────────────┐\n"
        f"│ {index}. {md_escape(link)}\n"
        f"└────────────────────────────────┘"
    )
    return card


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
        greeting = f"Hey {username}! 👋" if username else get_text('welcome_back', lang)
        
        menu_text = f"{prefix_message}{greeting}\n\n"
        menu_text += get_text('bot_title', lang) + "\n"
        menu_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        if session:
            try:
                user = session.query(TelegramUser).filter_by(id=user_id).first()
                if user:
                    # Check premium status using star_payments table
                    premium_check = session.execute(text("""
                        SELECT COUNT(*) FROM star_payments 
                        WHERE user_id = :user_id 
                        AND package_type LIKE 'premium_%' 
                        AND status = 'completed'
                        AND completed_at > NOW() - INTERVAL '30 days'
                    """), {'user_id': user.id}).scalar()
                    is_premium = premium_check > 0
                    
                    if is_premium:
                        menu_text += "╔═════════════╗\n"
                        menu_text += "  💎 PREMIUM USER  \n"
                        menu_text += "╚═════════════╝\n"
                    else:
                        points_bar = get_animated_progress_bar(user.points, 3, 10)
                        percentage = int((user.points / 3) * 100)
                        menu_text += f"💰 *Points:* {user.points}/3\n"
                        menu_text += f"[{points_bar}] {percentage}%\n"
                    
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

        is_premium = False
        if session:
            try:
                user = session.query(TelegramUser).filter_by(id=user_id).first()
                if user:
                    # Check premium status using star_payments table
                    premium_check = session.execute(text("""
                        SELECT COUNT(*) FROM star_payments 
                        WHERE user_id = :user_id 
                        AND package_type LIKE 'premium_%' 
                        AND status = 'completed'
                        AND completed_at > NOW() - INTERVAL '30 days'
                    """), {'user_id': user.id}).scalar()
                    is_premium = premium_check > 0
            except:
                pass

        button_rows = [
            [{"text": get_text('check_live', lang), "callback_data": "check_live"}],
            [
                {"text": get_text('my_account', lang), "callback_data": "my_account"},
                {"text": get_text('referrals', lang), "callback_data": "referrals"}
            ]
        ]
        
        if is_premium:
            button_rows.append([{"text": "🔄 Renew Premium", "callback_data": "buy"}])
        else:
            button_rows.append([{"text": "⭐ Buy Premium", "callback_data": "buy"}])
        
        button_rows.append([
            {"text": get_text('help', lang), "callback_data": "help"},
            {"text": get_text('settings', lang), "callback_data": "settings"}
        ])
        
        buttons = {"inline_keyboard": button_rows}
        
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
                
                join_button = {"inline_keyboard": [[{"text": "✅ Join Community Group", "url": REQUIRED_GROUP_URL}]]}
                await helper.send_message(sender_id, join_text, parse_mode="Markdown", reply_markup=join_button)
                return

        user = session.query(TelegramUser).filter_by(id=sender_id).first()
        
        prefix_message = ""
        username = from_user.get('first_name', 'there')
        
        if not user:
            referred_by_id = None
            text = message.get('text', '')
            if text and len(text.split()) > 1:
                try:
                    referred_by_id = int(text.split()[1])
                    if referred_by_id == sender_id:
                        referred_by_id = None
                except (ValueError, IndexError):
                    referred_by_id = None

            user_lang = detect_language(from_user.get('language_code', 'en'))

            user = TelegramUser(
                id=sender_id,
                username=from_user.get('username'),
                first_name=from_user.get('first_name'),
                points=DEFAULT_DAILY_POINTS,
                last_seen=datetime.now(timezone.utc),
                referred_by_id=referred_by_id,
                language=user_lang
            )
            session.add(user)
            session.commit()
            
            logger.info(f"New user created: {user.id} (@{user.username}) with detected language: {user_lang}")

            if referred_by_id:
                referrer = session.query(TelegramUser).filter_by(id=referred_by_id).first()
                if referrer:
                    referrer.points += REFERRAL_BONUS_POINTS
                    session.commit()
                    
                    referrer_msg = f"🎊 *Referral Success!*\n\n"
                    referrer_msg += f"{username} just joined using your referral link!\n\n"
                    referrer_msg += "💰 *Reward:* +5 Points\n"
                    referrer_msg += f"💎 *New Balance:* {referrer.points} points"
                    
                    await send_user_feedback(referrer.id, referrer_msg)
                    logger.info(f"Awarded 5 referral points to {referrer.id}")
                    
                    new_referral_count = session.query(TelegramUser).filter_by(referred_by_id=referrer.id).count()
                    await send_referral_milestone_notification(session, referrer.id, new_referral_count)

            welcome_text = "🎉 *Welcome to IGLiveZBot!*\n\n"
            welcome_text += f"Hey {username}! Great to have you here.\n\n"
            welcome_text += "🌍 *Please select your preferred language:*"
            
            lang_buttons = []
            languages = list(LANGUAGE_NAMES.items())
            for i in range(0, len(languages), 2):
                row = []
                for j in range(2):
                    if i + j < len(languages):
                        lang_code, lang_name = languages[i + j]
                        display_name = f"✓ {lang_name}" if lang_code == user_lang else lang_name
                        row.append({"text": display_name, "callback_data": f"setlang:{lang_code}"})
                lang_buttons.append(row)
            
            buttons = {"inline_keyboard": lang_buttons}
            
            await helper.send_message(sender_id, welcome_text, parse_mode="Markdown", reply_markup=buttons)
            logger.info(f"Sent language selection to new user {user.id}")
            return

        elif is_new_day_for_user(user):
            user.points = DEFAULT_DAILY_POINTS
            user.last_seen = datetime.now(timezone.utc)
            session.commit()
            
            prefix_message = get_text('good_morning', user.language) + "\n\n"
            prefix_message += get_text('daily_reset', user.language) + "\n\n"
            prefix_message += get_text('daily_bonus', user.language) + "\n\n"
            
            referral_count = session.query(TelegramUser).filter_by(referred_by_id=user.id).count()
            if referral_count >= 25 and referral_count < FREE_PREMIUM_REFERRAL_THRESHOLD:
                prefix_message += f"🎯 *You're so close!* Only {FREE_PREMIUM_REFERRAL_THRESHOLD - referral_count} more referrals for free Premium!\n\n"
            elif referral_count >= 10 and referral_count < 25:
                prefix_message += "💡 *Tip:* Keep referring friends to unlock free Premium at 30 referrals!\n\n"
            
            logger.info(f"Reset daily points for user {user.id}")
        else:
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

        now_utc = datetime.now(timezone.utc)
        if user.subscription_end:
            sub_end = user.subscription_end if user.subscription_end.tzinfo else user.subscription_end.replace(tzinfo=timezone.utc)
            is_unlimited = sub_end > now_utc
        else:
            is_unlimited = False
        
        referral_count = session.query(TelegramUser).filter_by(referred_by_id=user.id).count()
        
        account_text = "👤 *YOUR ACCOUNT*\n"
        account_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        account_text += f"👤 *Name:* {user.first_name}\n"
        account_text += f"🆔 *Username:* @{user.username or 'Not set'}\n"
        account_text += f"🔢 *User ID:* `{user.id}`\n"
        account_text += f"📅 *Joined:* {user.last_seen.strftime('%b %d, %Y') if user.last_seen else 'Unknown'}\n"
        account_text += f"👥 *Referrals:* {referral_count} friends\n\n"
        
        if is_unlimited:
            account_text += "╔═════════════╗\n"
            account_text += "  💎 PREMIUM USER  \n"
            account_text += "╚═════════════╝\n\n"
            account_text += f"✅ Unlimited Checks\n"
            account_text += f"📅 Premium Active\n"
            account_text += f"⏳ Valid for 30 days from last payment\n"
        else:
            points_bar = get_animated_progress_bar(user.points, 3, 10)
            percentage = int((user.points / 3) * 100)
            account_text += "💰 *FREE ACCOUNT*\n"
            account_text += "━━━━━━━━━━━━━━━━━━━━\n"
            account_text += f"💎 Points: *{user.points}/3*\n"
            account_text += f"[{points_bar}] {percentage}%\n"
            account_text += f"🔄 Resets: Daily at midnight UTC\n\n"
            account_text += "❌ *What you're missing:*\n"
            account_text += "  • Unlimited checks\n"
            account_text += "  • No daily limits\n"
            account_text += "  • Priority features\n"
        
        if not is_unlimited:
            account_text += "\n💡 *Tip:* Refer friends to earn bonus points!"
        else:
            account_text += "\n✨ *Enjoying Premium?* Share with friends!"
        
        if is_unlimited:
            buttons = {
                "inline_keyboard": [
                    [{"text": "🔄 Renew Premium", "callback_data": "buy"}],
                    [{"text": "🎁 Get Referral Link", "callback_data": "referrals"}],
                    [{"text": "⬅️ Back to Menu", "callback_data": "back"}]
                ]
            }
        else:
            buttons = {
                "inline_keyboard": [
                    [{"text": "⭐ Buy Points/Premium", "callback_data": "buy"}],
                    [{"text": "🎁 Get Referral Link", "callback_data": "referrals"}],
                    [{"text": "⬅️ Back to Menu", "callback_data": "back"}]
                ]
            }
        
        try:
            await helper.edit_message_text(chat_id, message_id, account_text, parse_mode="Markdown", reply_markup=buttons)
            logger.info(f"Edited message with account details for user {user.id}")
        except Exception as e:
            logger.error(f"Error editing account message: {e}")
            try:
                await helper.send_message(sender_id, account_text, parse_mode="Markdown", reply_markup=buttons)
            except:
                await helper.send_message(sender_id, "⚠️ Error loading account. Please try /start")

    except Exception as e:
        logger.error(f"Error in my_account_handler for user {sender_id}: {e}", exc_info=True)
        raise


async def check_live_handler(session: Session, payload: dict):
    """Displays currently live Instagram users with card-style formatting."""
    try:
        callback_query = payload.get('callback_query', {})
        from_user = callback_query.get('from', {})
        sender_id = from_user.get('id')
        message = callback_query.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        message_id = message.get('message_id')
        
        # Define now_utc at the beginning to avoid UnboundLocalError
        now_utc = datetime.now(timezone.utc)

        if not sender_id:
            logger.error("Could not determine sender_id from payload.")
            return
        
        # Rate limiting for live checks
        if not rate_limiter.is_allowed(sender_id, 'check_live'):
            reset_time = rate_limiter.get_reset_time(sender_id, 'check_live')
            error_msg = f"⚠️ *Too many requests!*\n\nPlease wait {reset_time} seconds before checking again."
            helper = TelegramHelper()
            try:
                await helper.edit_message_text(chat_id, message_id, error_msg, parse_mode="Markdown")
            except:
                pass
            return

        helper = TelegramHelper()

        # Show loading state
        try:
            await helper.edit_message_text(chat_id, message_id, "⏳ *Loading live streams...*\n\nPlease wait a moment.", parse_mode="Markdown")
        except:
            pass

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

        # Check premium status using star_payments table
        premium_check = session.execute(text("""
            SELECT COUNT(*) FROM star_payments 
            WHERE user_id = :user_id 
            AND package_type LIKE 'premium_%' 
            AND status = 'completed'
            AND completed_at > NOW() - INTERVAL '30 days'
        """), {'user_id': user.id}).scalar()
        is_unlimited = premium_check > 0
            
        # Apply rate limiting to actual live check logic
        if not rate_limiter.is_allowed(sender_id, 'live_check_logic'):
            reset_time = rate_limiter.get_reset_time(sender_id, 'live_check_logic')
            error_msg = f"⚠️ *Too many requests!*\n\nPlease wait {reset_time} seconds before checking again."
            try:
                await helper.edit_message_text(chat_id, message_id, error_msg, parse_mode="Markdown")
            except:
                pass
            return
            
        if not is_unlimited and page == 1:
            if user.points > 0:
                user.points -= 1
                session.commit()
                
                if user.points == 1:
                    tip_msg = "⚠️ *Low Points Alert!*\n\n"
                    tip_msg += "You have only *1 point* left today.\n\n"
                    tip_msg += "💡 *Quick tip:* Refer a friend to get +5 points instantly!\n\n"
                    tip_msg += "Or upgrade to Premium for unlimited checks."
                    
                    tip_buttons = {
                        "inline_keyboard": [
                            [{"text": "🎁 Get Referral Link", "callback_data": "referrals"}],
                            [{"text": "🌟 View Premium", "callback_data": "buy"}]
                        ]
                    }
                    try:
                        await helper.send_message(sender_id, tip_msg, parse_mode="Markdown", reply_markup=tip_buttons)
                    except:
                        pass
            else:
                tomorrow_utc = (now_utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                time_until_reset = tomorrow_utc - now_utc
                hours = int(time_until_reset.total_seconds() // 3600)
                minutes = int((time_until_reset.total_seconds() % 3600) // 60)
                
                no_points_msg = "😢 *No Points Left!*\n\n"
                no_points_msg += "You're missing live streams right now!\n\n"
                no_points_msg += f"⏰ *Points reset in:* {hours}h {minutes}m\n\n"
                no_points_msg += "🌟 *UPGRADE TO PREMIUM:*\n"
                no_points_msg += "  ✅ Unlimited checks 24/7\n"
                no_points_msg += "  ⚡ Never miss a stream\n"
                no_points_msg += "  💎 Only ⭐150 for 7 days\n\n"
                no_points_msg += "🎁 *Or refer a friend:* Get +5 points instantly\n"
                
                buttons = {
                    "inline_keyboard": [
                        [{"text": "🌟 Upgrade Now", "callback_data": "buy"}],
                        [{"text": "🎁 Get Referral Link", "callback_data": "referrals"}],
                        [{"text": "⬅️ Back", "callback_data": "back"}]
                    ]
                }
                
                logger.info(f"User {user.id} has no points left.")
                last_live = user_data.get('last_live_at')
                
                live_message += create_stream_card(username, link, total_lives, last_live, idx)
                live_message += "\n\n"
        else:
            live_message = "🔴 *LIVE NOW*\n"
            live_message += "━━━━━━━━━━━━━━━━━━━━\n\n"
            live_message += "     🌙\n"
            live_message += "   ✨ 💤 ✨\n\n"
            live_message += "😴 *No one is live right now.*\n\n"
            if is_unlimited:
                live_message += "💡 *What you can do:*\n"
                live_message += "  • Check back in a few minutes\n"
                live_message += "  • Streams are tracked 24/7\n"
                live_message += "  • Share with friends\n"
            else:
                live_message += "💡 *What you can do:*\n"
                live_message += "  • Check back in a few minutes\n"
                live_message += "  • Upgrade for instant notifications\n"
                live_message += "  • Invite friends for bonus points\n"
        
        now_utc = datetime.now(timezone.utc)
        tomorrow_utc = (now_utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        time_until_reset = tomorrow_utc - now_utc
        hours = int(time_until_reset.total_seconds() // 3600)
        minutes = int((time_until_reset.total_seconds() % 3600) // 60)
        
        live_message += "\n━━━━━━━━━━━━━━━━━━━━\n"
        if is_unlimited:
            live_message += f"💎 *Status:* Premium (Unlimited)\n"
        else:
            live_message += f"💰 *Points Left:* {user.points}/3\n"
            live_message += f"⏰ *Reset in:* {hours}h {minutes}m\n"
        
        live_message += f"🔄 *Updated:* {datetime.now(timezone.utc).strftime('%I:%M %p UTC')}"
        
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
        
        try:
            await helper.edit_message_text(chat_id, message_id, live_message, parse_mode="Markdown", reply_markup=buttons)
            logger.info(f"User {user.id} checked live users page {page}/{total_pages}. Total: {total_users} live. Points: {user.points}")
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            try:
                await helper.send_message(sender_id, live_message, parse_mode="Markdown", reply_markup=buttons)
            except Exception as e2:
                logger.error(f"Error sending fallback message: {e2}")
                await helper.send_message(sender_id, "⚠️ An error occurred. Please try /start to restart the bot.")

    except Exception as e:
        logger.error(f"Error in check_live_handler for user {sender_id}: {e}", exc_info=True)
        session.rollback()
        raise


async def referrals_handler(session: Session, payload: dict):
    """Displays referral information with animated progress bar."""
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

        referral_count = session.query(TelegramUser).filter_by(referred_by_id=user.id).count()
        
        referral_text = "🎁 *REFERRALS*\n"
        referral_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        referral_text += f"👥 *Total Referrals:* {referral_count}\n"
        referral_text += f"💰 *Points Earned:* {referral_count * 5}\n\n"
        
        if referral_count < FREE_PREMIUM_REFERRAL_THRESHOLD:
            progress_bar = get_animated_progress_bar(referral_count, FREE_PREMIUM_REFERRAL_THRESHOLD, 15)
            percentage = int((referral_count / FREE_PREMIUM_REFERRAL_THRESHOLD) * 100)
            referral_text += f"🎯 *Progress to Free Premium:*\n"
            referral_text += f"[{progress_bar}] {percentage}%\n"
            referral_text += f"*{referral_count}/{FREE_PREMIUM_REFERRAL_THRESHOLD}* referrals\n\n"
        else:
            referral_text += "🏆 *Achievement Unlocked!*\n"
            referral_text += "   You've earned free premium! 🎉\n\n"
        
        referral_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        referral_text += "💡 *How it works:*\n\n"
        referral_text += "1️⃣ Share your link\n"
        referral_text += "2️⃣ Friend joins via link\n"
        referral_text += "3️⃣ You both get +5 points!\n"
        referral_text += f"🎁 {FREE_PREMIUM_REFERRAL_THRESHOLD} referrals = Free 7-day Premium!\n\n"
        
        bot_username = BOT_USERNAME
        referral_link = f"https://t.me/{bot_username}?start={user.id}"
        
        referral_text += "🔗 *Your Referral Link:*\n"
        referral_text += f"`{referral_link}`\n\n"
        referral_text += "_(Tap to copy)_"
        
        buttons = {
            "inline_keyboard": [
                [{"text": "📤 Share Link", "url": f"https://t.me/share/url?url={referral_link}&text=Join me on IGLiveZBot!"}],
                [{"text": "⬅️ Back to Menu", "callback_data": "back"}]
            ]
        }
        try:
            await helper.edit_message_text(chat_id, message_id, referral_text, parse_mode="Markdown", reply_markup=buttons)
        except Exception as e:
            logger.error(f"Error editing referral message: {e}")
            try:
                await helper.send_message(sender_id, referral_text, parse_mode="Markdown", reply_markup=buttons)
            except:
                await helper.send_message(sender_id, "⚠️ Error loading referrals. Please try /start")

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
        help_text += "   +5 points per friend\n\n"
        
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
                [{"text": "💬 Join Support Group", "url": REQUIRED_GROUP_URL}],
                [{"text": "⬅️ Back to Menu", "callback_data": "back"}]
            ]
        }
        try:
            await helper.edit_message_text(chat_id, message_id, help_text, parse_mode="Markdown", reply_markup=buttons)
        except Exception as e:
            logger.error(f"Error editing help message: {e}")
            try:
                await helper.send_message(sender_id, help_text, parse_mode="Markdown", reply_markup=buttons)
            except:
                await helper.send_message(sender_id, "⚠️ Error loading help. Please try /start")

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

        # Check if user is premium using star_payments
        premium_check = session.execute(text("""
            SELECT COUNT(*) FROM star_payments 
            WHERE user_id = :user_id 
            AND package_type LIKE 'premium_%' 
            AND status = 'completed'
            AND completed_at > NOW() - INTERVAL '30 days'
        """), {'user_id': user.id}).scalar()
        is_premium = premium_check > 0
        
        settings_text = "⚙️ *SETTINGS*\n"
        settings_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        settings_text += f"🌍 *Language:* {LANGUAGE_NAMES.get(user.language, 'English')}\n"
        
        if is_premium:
            notifications_enabled = getattr(user, 'notifications_enabled', True)
            notifications_status = "🔔 ON" if notifications_enabled else "🔕 OFF"
            settings_text += f"🔔 *Live Notifications:* {notifications_status}\n"
        
        settings_text += "\nChoose an option below:"

        button_rows = [
            [{"text": "🌍 Change Language", "callback_data": "lang:select"}]
        ]
        
        if is_premium:
            notifications_enabled = getattr(user, 'notifications_enabled', True)
            toggle_text = "🔕 Turn OFF Notifications" if notifications_enabled else "🔔 Turn ON Notifications"
            button_rows.append([{"text": toggle_text, "callback_data": "toggle_notifications"}])
        
        button_rows.append([{"text": "⬅️ Back to Menu", "callback_data": "back"}])
        
        buttons = {"inline_keyboard": button_rows}
        try:
            await helper.edit_message_text(chat_id, message_id, settings_text, parse_mode="Markdown", reply_markup=buttons)
        except Exception as e:
            logger.error(f"Error editing settings message: {e}")
            try:
                await helper.send_message(sender_id, settings_text, parse_mode="Markdown", reply_markup=buttons)
            except:
                await helper.send_message(sender_id, "⚠️ Error loading settings. Please try /start")

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

        lang_code = callback_data.split(':')[1] if ':' in callback_data else 'en'

        user = session.query(TelegramUser).filter_by(id=sender_id).first()
        if user:
            user.language = lang_code
            session.commit()
            logger.info(f"User {user.id} set initial language to {lang_code}")

        prefix_message = get_text('language_set', lang_code) + "\n\n"
        await send_main_menu(sender_id, prefix_message, username, lang_code, session)

    except Exception as e:
        logger.error(f"Error in set_initial_language_handler: {e}", exc_info=True)
        raise


async def clear_notifications_handler(session: Session, payload: dict):
    """Clears all notification messages for the user. TEMPORARILY DISABLED."""
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
        
        # TEMPORARILY DISABLED - Function was causing 30+ second delays
        info_msg = "ℹ️ *Clear function temporarily disabled*\n\nThis feature is being optimized for better performance."
        
        try:
            await helper.edit_message_text(chat_id, message_id, info_msg, parse_mode="Markdown")
        except:
            pass
        
        logger.info(f"User {sender_id} attempted to clear notifications (function disabled)")

    except Exception as e:
        logger.error(f"Error in clear_notifications_handler: {e}", exc_info=True)


async def toggle_notifications_handler(session: Session, payload: dict):
    """Handles notification toggle for premium users."""
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

        # Toggle notifications (handle missing column)
        current_status = getattr(user, 'notifications_enabled', True)
        user.notifications_enabled = not current_status
        session.commit()
        
        status = "enabled" if user.notifications_enabled else "disabled"
        icon = "🔔" if user.notifications_enabled else "🔕"
        
        confirm_text = f"{icon} *Notifications {status.title()}!*\n\n"
        if user.notifications_enabled:
            confirm_text += "You'll now receive live stream alerts.\n\n"
        else:
            confirm_text += "You won't receive live stream alerts.\n\n"
        
        # Show updated settings menu
        await settings_handler(session, payload)
        
        logger.info(f"User {user.id} {status} notifications")

    except Exception as e:
        logger.error(f"Error in toggle_notifications_handler: {e}", exc_info=True)
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

        if callback_data == "lang:select":
            lang_text = "🌍 *SELECT LANGUAGE*\n"
            lang_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            lang_text += "Choose your preferred language:"

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
            
            try:
                await helper.edit_message_text(chat_id, message_id, lang_text, parse_mode="Markdown", reply_markup=buttons)
            except Exception as e:
                logger.error(f"Error editing language selection: {e}")
                try:
                    await helper.send_message(sender_id, lang_text, parse_mode="Markdown", reply_markup=buttons)
                except:
                    await helper.send_message(sender_id, "⚠️ Error loading languages. Please try /start")
        else:
            lang_code = callback_data.split(':')[1] if ':' in callback_data else user.language
            user.language = lang_code
            session.commit()
            logger.info(f"User {user.id} changed language to {lang_code}")

            confirm_text = get_text('language_changed', lang_code) + "\n\n"
            confirm_text += "⚙️ *SETTINGS*\n"
            confirm_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            confirm_text += f"🌍 *Current Language:* {LANGUAGE_NAMES.get(lang_code, 'English')}\n\n"
            confirm_text += "Choose an option below:"

            buttons = {
                "inline_keyboard": [
                    [{"text": get_text('change_language', lang_code), "callback_data": "lang:select"}],
                    [{"text": get_text('back', lang_code), "callback_data": "back"}]
                ]
            }
            try:
                await helper.edit_message_text(chat_id, message_id, confirm_text, parse_mode="Markdown", reply_markup=buttons)
            except Exception as e:
                logger.error(f"Error editing language confirmation: {e}")
                try:
                    await helper.send_message(sender_id, confirm_text, parse_mode="Markdown", reply_markup=buttons)
                except:
                    await helper.send_message(sender_id, "⚠️ Language changed but display error occurred. Please try /start")

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




async def handle_broadcast_command(session: Session, payload: dict):
    """Handles the /broadcast command for admins only."""
    try:
        message = payload.get('message', {})
        from_user = message.get('from', {})
        sender_id = from_user.get('id')
        text = message.get('text', '').strip()
        
        if not sender_id:
            logger.error("Could not determine sender_id from payload.")
            return

        # Check if user is admin
        if sender_id not in ADMIN_IDS:
            logger.warning(f"Unauthorized broadcast attempt from user {sender_id}")
            await send_user_feedback(sender_id, "❌ You are not authorized to use this command.")
            return

        # Parse broadcast message (everything after /broadcast)
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            await send_user_feedback(
                sender_id, 
                "ℹ️ *Broadcast Usage*\\n\\n"
                "Send: `/broadcast your message here`\\n\\n"
                "Your message will be sent to all users."
            )
            return
        
        broadcast_text = parts[1]
        
        # Create a job to broadcast the message
        from models import Job
        import json
        
        new_job = Job(
            job_type='broadcast_message',
            payload=json.dumps({'message': broadcast_text}),
            status='pending'
        )
        session.add(new_job)
        session.commit()
        
        # Count total users for feedback
        total_users = session.query(TelegramUser).count()
        
        confirm_msg = f"📢 *Broadcast Queued!*\\n\\n"
        confirm_msg += f"Message will be sent to *{total_users}* users.\\n\\n"
        confirm_msg += f"_Preview:_\\n{broadcast_text[:100]}{'...' if len(broadcast_text) > 100 else ''}"
        
        await send_user_feedback(sender_id, confirm_msg)
        logger.info(f"Admin {sender_id} queued broadcast to {total_users} users")

    except Exception as e:
        logger.error(f"Error in handle_broadcast_command: {e}", exc_info=True)
        try:
            await send_user_feedback(sender_id, "❌ Failed to queue broadcast. Check logs.")
        except:
            pass
        raise


async def broadcast_message_handler(session: Session, payload: dict):
    """Handles broadcasting messages to all users."""
    try:
        message_text = payload.get('message', '')
        if not message_text:
            logger.warning("No message text provided for broadcast.")
            return

        users = session.query(TelegramUser).all()
        helper = TelegramHelper()
        
        success_count = 0
        fail_count = 0
        
        for user in users:
            try:
                await helper.send_message(user.id, message_text, parse_mode="Markdown")
                success_count += 1
                await asyncio.sleep(0.2)
            except Exception as e:
                logger.error(f"Failed to send broadcast to user {user.id}: {e}")
                fail_count += 1
        
        logger.info(f"Broadcast completed. Success: {success_count}, Failed: {fail_count}")

    except Exception as e:
        logger.error(f"Error in broadcast_message_handler: {e}", exc_info=True)
        raise


async def init_handler(session: Session, payload: dict):
    """Handles /init command."""
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
    """Handles /activate command."""
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


async def delete_previous_live_notifications(session: Session, helper: TelegramHelper, username: str):
    """Delete previous live notification messages for a username."""
    try:
        previous_messages = session.query(LiveNotificationMessage).filter_by(username=username).all()
        for msg in previous_messages:
            try:
                await helper.delete_message(msg.group_id, msg.message_id)
            except:
                pass
        session.query(LiveNotificationMessage).filter_by(username=username).delete()
        session.commit()
    except Exception as e:
        logger.error(f"Error deleting previous notifications for {username}: {e}")

async def save_live_notification_message(session: Session, username: str, group_id: str, message_id: int):
    """Save live notification message ID for tracking."""
    try:
        existing = session.query(LiveNotificationMessage).filter_by(username=username, group_id=group_id).first()
        if existing:
            existing.message_id = message_id
            existing.created_at = datetime.now()
        else:
            new_msg = LiveNotificationMessage(username=username, group_id=group_id, message_id=message_id)
            session.add(new_msg)
        session.commit()
    except Exception as e:
        logger.error(f"Error saving notification message: {e}")

async def notify_live_handler(session: Session, payload: dict):
    """Send live notifications to premium users."""
    try:
        username = payload.get('username')
        link = payload.get('link')
        
        if not username or not link:
            logger.error(f"Invalid notify_live payload: {payload}")
            return
        
        helper = TelegramHelper()
        
        # Delete previous notifications for this username
        await delete_previous_live_notifications(session, helper, username)
        
        query = text("""
            SELECT DISTINCT u.id, u.first_name, u.language 
            FROM telegram_users u
            JOIN star_payments sp ON u.id = sp.user_id
            WHERE sp.package_type LIKE 'premium_%'
            AND sp.status = 'completed'
            AND sp.completed_at > NOW() - INTERVAL '30 days'
            AND u.notifications_enabled = TRUE
        """)
        premium_users = session.execute(query).fetchall()
        
        if not premium_users:
            logger.info(f"No premium users to notify for {username}")
            return
        
        logger.info(f"🔴 Notifying {len(premium_users)} premium users about {username}")
        
        success_count = 0
        
        for user_id, first_name, lang in premium_users:
            try:
                notification = f"🔴 *LIVE NOW!*\n\n"
                notification += f"*{username}* just started streaming!\n\n"
                notification += f"[Watch Now]({link})"
                
                buttons = {
                    "inline_keyboard": [[
                        {"text": "🔕 Turn OFF", "callback_data": "toggle_notifications"},
                        {"text": "🗑️ Clear All", "callback_data": "clear_notifications"}
                    ]]
                }
                result = await helper.send_message(user_id, notification, parse_mode="Markdown", reply_markup=buttons)
                if result and result.get('ok'):
                    msg_id = result['result']['message_id']
                    success_count += 1
                    
                    # Schedule auto-delete
                    try:
                        delete_time = datetime.now(timezone.utc) + timedelta(minutes=5)
                        ephemeral = EphemeralMessage(
                            chat_id=user_id,
                            message_id=msg_id,
                            delete_at=delete_time
                        )
                        session.add(ephemeral)
                    except Exception as e:
                        logger.error(f"Failed to schedule deletion for {user_id}: {e}")

                await asyncio.sleep(0.2)
            except Exception as e:
                logger.error(f"Failed to notify user {user_id}: {e}")
        
        session.commit()
        logger.info(f"✅ Sent {success_count}/{len(premium_users)} notifications for {username}")
        
    except Exception as e:
        logger.error(f"Error in notify_live_handler: {e}", exc_info=True)
        raise


async def check_and_trigger_auto_broadcast(session: Session):
    """
    Checks if live stream count exceeds threshold and triggers an automated broadcast
    if the cooldown period has passed.
    """
    try:
        # 1. Check live count
        live_count = session.execute(text("SELECT COUNT(*) FROM insta_links WHERE is_live = TRUE")).scalar()
        
        if live_count < AUTO_BROADCAST_THRESHOLD:
            return

        # 2. Check cooldown
        last_broadcast_setting = session.query(SystemSettings).filter_by(key='last_auto_broadcast').first()
        now = datetime.now(timezone.utc)
        
        if last_broadcast_setting and last_broadcast_setting.updated_at:
            last_time = last_broadcast_setting.updated_at
            if last_time.tzinfo is None:
                last_time = last_time.replace(tzinfo=timezone.utc)
            
            # Calculate hours since last broadcast
            hours_diff = (now - last_time).total_seconds() / 3600
            
            if hours_diff < AUTO_BROADCAST_COOLDOWN_HOURS:
                # Cooldown active
                return

        # 3. Trigger Broadcast
        logger.info(f"🔥 Triggering Auto-Broadcast! Live count: {live_count}")
        
        broadcast_text = f"🔥 *IT'S POPPING OFF!*\n\n"
        broadcast_text += f"There are currently *{live_count}* models live right now! 📸\n\n"
        broadcast_text += "Don't miss the action - check who's streaming!"
        
        # Create broadcast job
        from models import Job
        import json
        
        new_job = Job(
            job_type='broadcast_message',
            payload=json.dumps({'message': broadcast_text}),
            status='pending'
        )
        session.add(new_job)
        
        # Update timestamp
        if last_broadcast_setting:
            last_broadcast_setting.updated_at = now
            # Force update if value didn't change (though updated_at should handle it)
            last_broadcast_setting.value = str(live_count) 
        else:
            new_setting = SystemSettings(key='last_auto_broadcast', value=str(live_count), updated_at=now)
            session.add(new_setting)
            
        session.commit()
        logger.info(f"Auto-broadcast queued successfully.")

    except Exception as e:
        logger.error(f"Error in check_and_trigger_auto_broadcast: {e}", exc_info=True)

