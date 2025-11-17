# Production-ready handlers with all critical issues fixed
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from models import TelegramUser, ChatGroup
from telegram_helper import TelegramHelper
from translations import get_text, detect_language, LANGUAGE_NAMES
from smart_notifications import send_referral_milestone_notification
from rate_limiter import rate_limiter
from config import (
    BOT_USERNAME, REQUIRED_GROUP_URL, REQUIRED_GROUP_ID, REQUIRE_GROUP_MEMBERSHIP,
    LIVE_STREAMS_PER_PAGE, PREMIUM_VALIDITY_DAYS,
    DEFAULT_DAILY_POINTS, REFERRAL_BONUS_POINTS, FREE_PREMIUM_REFERRAL_THRESHOLD
)

logger = logging.getLogger(__name__)

def check_premium_status(session: Session, user_id: int) -> bool:
    """Check if user has active premium subscription - database agnostic"""
    try:
        # Use database-agnostic date arithmetic
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=PREMIUM_VALIDITY_DAYS)
        premium_check = session.execute(text("""
            SELECT COUNT(*) FROM star_payments 
            WHERE user_id = :user_id 
            AND package_type LIKE 'premium_%' 
            AND status = 'completed'
            AND completed_at > :cutoff_date
        """), {'user_id': user_id, 'cutoff_date': cutoff_date}).scalar()
        return premium_check > 0
    except SQLAlchemyError as e:
        logger.error(f"Database error checking premium status for user {user_id}: {e}")
        return False

def safe_divide(numerator: int, denominator: int, default: int = 0) -> int:
    """Safe division to prevent ZeroDivisionError"""
    if denominator == 0:
        return default
    return int((numerator / denominator) * 10)

async def send_main_menu(user_id: int, prefix_message: str = "", username: str = None, lang: str = 'en', session: Session = None):
    """Send main menu with fixed premium detection and error handling"""
    try:
        greeting = f"Hey {username}! 👋" if username else get_text('welcome_back', lang)
        menu_text = f"{prefix_message}{greeting}\n\n"
        menu_text += get_text('bot_title', lang) + "\n━━━━━━━━━━━━━━━━━━━━\n\n"
        
        is_premium = False
        if session:
            try:
                user = session.query(TelegramUser).filter_by(id=user_id).first()
                if user:
                    is_premium = check_premium_status(session, user.id)
                    if is_premium:
                        menu_text += "╔═════════════╗\n  💎 PREMIUM USER  \n╚═════════════╝\n"
                    else:
                        points_bar = "▰" * safe_divide(user.points, max(1, DEFAULT_DAILY_POINTS))
                        menu_text += f"💰 *Points:* {user.points}/{DEFAULT_DAILY_POINTS}\n[{points_bar}]\n"
            except SQLAlchemyError as e:
                logger.error(f"Database error in send_main_menu: {e}")
        
        menu_text += get_text('choose_option', lang)
        
        button_rows = [
            [{"text": get_text('check_live', lang), "callback_data": "check_live"}],
            [{"text": get_text('my_account', lang), "callback_data": "my_account"}],
            [{"text": "⭐ Premium" if not is_premium else "🔄 Renew", "callback_data": "buy"}]
        ]
        
        helper = TelegramHelper()
        await helper.send_message(user_id, menu_text, parse_mode="Markdown", 
                                reply_markup={"inline_keyboard": button_rows})
        
    except Exception as e:
        logger.error(f"Error in send_main_menu: {e}")
        raise

async def check_live_handler(session: Session, payload: dict):
    """Fixed check live handler with proper transactions and error handling"""
    try:
        callback_query = payload.get('callback_query', {})
        sender_id = callback_query.get('from', {}).get('id')
        message = callback_query.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        message_id = message.get('message_id')

        if not sender_id:
            return

        # Rate limiting for callback
        if not rate_limiter.is_allowed(sender_id, 'check_live'):
            helper = TelegramHelper()
            reset_time = rate_limiter.get_reset_time(sender_id, 'check_live')
            error_msg = f"⚠️ *Rate limited!*\n\nWait {reset_time}s"
            try:
                await helper.edit_message_text(chat_id, message_id, error_msg, parse_mode="Markdown")
            except:
                pass
            return

        helper = TelegramHelper()
        
        try:
            user = session.query(TelegramUser).filter_by(id=sender_id).first()
            if not user:
                await helper.edit_message_text(chat_id, message_id, "❌ User not found. Use /start", parse_mode="Markdown")
                return

            is_premium = check_premium_status(session, user.id)
            
            # Rate limiting for actual live check logic
            if not rate_limiter.is_allowed(sender_id, 'live_check_logic'):
                reset_time = rate_limiter.get_reset_time(sender_id, 'live_check_logic')
                error_msg = f"⚠️ *Too many requests!*\n\nWait {reset_time}s"
                try:
                    await helper.edit_message_text(chat_id, message_id, error_msg, parse_mode="Markdown")
                except:
                    pass
                return

            # Points handling with proper transaction
            points_deducted = False
            if not is_premium:
                if user.points > 0:
                    user.points -= 1
                    points_deducted = True
                    # Don't commit yet - wait for successful operation
                else:
                    no_points_msg = "😢 *No Points Left!*\n\nUpgrade to Premium for unlimited checks!"
                    await helper.edit_message_text(chat_id, message_id, no_points_msg, parse_mode="Markdown")
                    return

            try:
                # Fetch live streams with all required fields
                query = text("""
                    SELECT username, link, total_lives, last_live_at 
                    FROM insta_links 
                    WHERE is_live = TRUE 
                    ORDER BY last_live_at DESC 
                    LIMIT :limit
                """)
                result = session.execute(query, {'limit': LIVE_STREAMS_PER_PAGE}).fetchall()
                
                if result:
                    live_message = "🔴 *LIVE NOW*\n━━━━━━━━━━━━━━━━━━━━\n\n"
                    for i, (username, link, total_lives, last_live_at) in enumerate(result, 1):
                        live_message += f"{i}. {username}\n{link}\n"
                        if total_lives:
                            live_message += f"📊 Lives: {total_lives}\n"
                        live_message += "\n"
                else:
                    live_message = "😴 *No one is live right now.*"
                
                live_message += f"\n💰 Points: {user.points}/{DEFAULT_DAILY_POINTS}" if not is_premium else "\n💎 Premium Active"
                
                # Only commit transaction after successful operation
                if points_deducted:
                    session.commit()
                
                await helper.edit_message_text(chat_id, message_id, live_message, parse_mode="Markdown")
                
            except SQLAlchemyError as e:
                logger.error(f"Database error fetching live users: {e}")
                # Rollback points deduction on database error
                if points_deducted:
                    session.rollback()
                
                error_msg = "⚠️ *Database Error*\n\nTry again in a moment.\nYour points were not deducted."
                await helper.edit_message_text(chat_id, message_id, error_msg, parse_mode="Markdown")
                
        except SQLAlchemyError as e:
            logger.error(f"Database error in check_live_handler: {e}")
            session.rollback()
            error_msg = "⚠️ *Service Error*\n\nPlease try again later."
            try:
                await helper.edit_message_text(chat_id, message_id, error_msg, parse_mode="Markdown")
            except:
                pass

    except Exception as e:
        logger.error(f"Error in check_live_handler: {e}")
        try:
            session.rollback()
        except:
            pass

async def clear_notifications_handler(session: Session, payload: dict):
    """Fixed clear notifications with proper validation"""
    try:
        callback_query = payload.get('callback_query', {})
        sender_id = callback_query.get('from', {}).get('id')
        message = callback_query.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        message_id = message.get('message_id')

        if not sender_id:
            return

        # Validate user can only clear in private chat
        if chat_id != sender_id:
            helper = TelegramHelper()
            error_msg = "❌ You can only clear notifications in private chat."
            try:
                await helper.edit_message_text(chat_id, message_id, error_msg, parse_mode="Markdown")
            except:
                pass
            return

        helper = TelegramHelper()
        cleared_count = 0
        
        # Clear recent messages
        for i in range(1, 101):
            try:
                await helper.delete_message(chat_id, message_id - i)
                cleared_count += 1
            except:
                pass

        result_text = f"✅ *Cleared {cleared_count} messages!*"
        try:
            await helper.edit_message_text(chat_id, message_id, result_text, parse_mode="Markdown")
        except:
            pass

    except Exception as e:
        logger.error(f"Error in clear_notifications_handler: {e}")

async def notify_live_handler(session: Session, payload: dict):
    """Fixed notify live handler with proper premium detection"""
    try:
        username = payload.get('username')
        link = payload.get('link')
        
        if not username or not link:
            return
        
        # Get premium users with notifications enabled - database agnostic
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=PREMIUM_VALIDITY_DAYS)
        query = text("""
            SELECT DISTINCT u.id, u.first_name, u.language 
            FROM telegram_users u
            JOIN star_payments sp ON u.id = sp.user_id
            WHERE sp.package_type LIKE 'premium_%'
            AND sp.status = 'completed'
            AND sp.completed_at > :cutoff_date
            AND u.notifications_enabled = TRUE
        """)
        premium_users = session.execute(query, {'cutoff_date': cutoff_date}).fetchall()
        
        if not premium_users:
            return
        
        helper = TelegramHelper()
        success_count = 0
        
        for user_id, first_name, lang in premium_users:
            try:
                notification = f"🔴 *LIVE NOW!*\n\n*{username}* started streaming!\n\n[Watch Now]({link})"
                buttons = {"inline_keyboard": [[
                    {"text": "🔕 Turn OFF", "callback_data": "toggle_notifications"},
                    {"text": "🗑️ Clear All", "callback_data": "clear_notifications"}
                ]]}
                
                await helper.send_message(user_id, notification, parse_mode="Markdown", reply_markup=buttons)
                success_count += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"Failed to notify user {user_id}: {e}")
        
        logger.info(f"✅ Sent {success_count}/{len(premium_users)} notifications for {username}")
        
    except Exception as e:
        logger.error(f"Error in notify_live_handler: {e}")