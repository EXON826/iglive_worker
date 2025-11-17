# smart_notifications.py
# Smart notification system for contextual user engagement

import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

from models import TelegramUser
from telegram_helper import TelegramHelper

logger = logging.getLogger(__name__)


async def send_point_reset_reminder(session: Session):
    """
    Send reminder to users 1 hour before point reset.
    Run this as a scheduled job at 23:00 UTC daily.
    """
    try:
        # Get users with 0 points who haven't upgraded
        query = text("""
            SELECT id, first_name, language
            FROM telegram_users
            WHERE points = 0
            AND (subscription_end IS NULL OR subscription_end < :now)
        """)
        
        result = session.execute(query, {'now': datetime.now(timezone.utc)}).fetchall()
        helper = TelegramHelper()
        
        for row in result:
            user_id, first_name, lang = row[0], row[1], row[2] or 'en'
            
            reminder_msg = f"⏰ *Hey {first_name}!*\n\n"
            reminder_msg += "Your points reset in 1 hour! 🎉\n\n"
            reminder_msg += "💎 You'll get 3 fresh points at midnight UTC.\n\n"
            reminder_msg += "💡 *Pro tip:* Upgrade to Premium for unlimited checks anytime!"
            
            try:
                await helper.send_message(user_id, reminder_msg, parse_mode="Markdown")
                logger.info(f"Sent reset reminder to user {user_id}")
            except Exception as e:
                logger.error(f"Failed to send reminder to {user_id}: {e}")
        
        logger.info(f"Point reset reminders sent to {len(result)} users")
        
    except Exception as e:
        logger.error(f"Error in send_point_reset_reminder: {e}", exc_info=True)


async def send_referral_milestone_notification(session: Session, user_id: int, referral_count: int):
    """
    Send notification when user reaches referral milestones.
    Call this after a successful referral.
    """
    try:
        user = session.query(TelegramUser).filter_by(id=user_id).first()
        if not user:
            return
        
        helper = TelegramHelper()
        milestone_msg = None
        
        # Milestone notifications
        if referral_count == 5:
            milestone_msg = "🎯 *Milestone Reached!*\n\n"
            milestone_msg += "You've referred 5 friends! 🎉\n\n"
            milestone_msg += "Keep going! 25 more for free Premium.\n"
            milestone_msg += f"Progress: [{referral_count}/30]"
        
        elif referral_count == 10:
            milestone_msg = "🔥 *You're on fire!*\n\n"
            milestone_msg += "10 referrals completed! Amazing work! 🌟\n\n"
            milestone_msg += "You're 1/3 of the way to free Premium!\n"
            milestone_msg += f"Progress: [{referral_count}/30]"
        
        elif referral_count == 20:
            milestone_msg = "🚀 *Almost there!*\n\n"
            milestone_msg += "20 referrals! You're crushing it! 💪\n\n"
            milestone_msg += "Just 10 more for FREE 7-day Premium!\n"
            milestone_msg += f"Progress: [{referral_count}/30]"
        
        elif referral_count == 25:
            milestone_msg = "⚡ *SO CLOSE!*\n\n"
            milestone_msg += "25 referrals! You're almost there! 🎊\n\n"
            milestone_msg += "Only 5 more friends for FREE Premium!\n"
            milestone_msg += f"Progress: [{referral_count}/30]"
        
        elif referral_count == 30:
            milestone_msg = "🏆 *ACHIEVEMENT UNLOCKED!*\n\n"
            milestone_msg += "30 REFERRALS COMPLETED! 🎉🎉🎉\n\n"
            milestone_msg += "You've earned FREE 7-day Premium!\n\n"
            milestone_msg += "Contact support to claim your reward! 💎"
        
        if milestone_msg:
            try:
                await helper.send_message(user_id, milestone_msg, parse_mode="Markdown")
                logger.info(f"Sent milestone notification to {user_id} for {referral_count} referrals")
            except Exception as e:
                logger.error(f"Failed to send milestone notification to {user_id}: {e}")
    
    except Exception as e:
        logger.error(f"Error in send_referral_milestone_notification: {e}", exc_info=True)


async def send_premium_expiry_warning(session: Session):
    """
    Send warning to premium users 3 days before expiry.
    Run this as a scheduled job daily.
    """
    try:
        now_utc = datetime.now(timezone.utc)
        three_days_later = now_utc + timedelta(days=3)
        
        query = text("""
            SELECT id, first_name, subscription_end, language
            FROM telegram_users
            WHERE subscription_end IS NOT NULL
            AND subscription_end > :now
            AND subscription_end <= :three_days
        """)
        
        result = session.execute(query, {
            'now': now_utc,
            'three_days': three_days_later
        }).fetchall()
        
        helper = TelegramHelper()
        
        for row in result:
            user_id, first_name, sub_end, lang = row[0], row[1], row[2], row[3] or 'en'
            days_left = (sub_end - now_utc).days
            
            warning_msg = f"⚠️ *Premium Expiring Soon*\n\n"
            warning_msg += f"Hey {first_name}! Your Premium subscription expires in {days_left} days.\n\n"
            warning_msg += "Don't lose access to unlimited checks! 🔴\n\n"
            warning_msg += "💡 Renew now and keep enjoying:\n"
            warning_msg += "  ✅ Unlimited live checks\n"
            warning_msg += "  ⚡ No daily limits\n"
            warning_msg += "  🔔 Priority support\n\n"
            warning_msg += "Tap below to renew! 👇"
            
            try:
                await helper.send_message(user_id, warning_msg, parse_mode="Markdown")
                logger.info(f"Sent expiry warning to user {user_id}")
            except Exception as e:
                logger.error(f"Failed to send expiry warning to {user_id}: {e}")
        
        logger.info(f"Premium expiry warnings sent to {len(result)} users")
        
    except Exception as e:
        logger.error(f"Error in send_premium_expiry_warning: {e}", exc_info=True)


async def send_contextual_tip(user_id: int, tip_type: str, **kwargs):
    """
    Send contextual tips based on user behavior.
    
    Tip types:
    - 'first_check': After first live check
    - 'frequent_user': After 5+ checks in a day
    - 'inactive': After 7 days of inactivity
    """
    try:
        helper = TelegramHelper()
        tip_msg = None
        
        if tip_type == 'first_check':
            tip_msg = "👋 *Welcome!*\n\n"
            tip_msg += "Great! You just checked your first live stream.\n\n"
            tip_msg += "💡 *Did you know?*\n"
            tip_msg += "  • You get 3 free checks daily\n"
            tip_msg += "  • Points reset at midnight UTC\n"
            tip_msg += "  • Refer friends for +5 bonus points\n\n"
            tip_msg += "Enjoy tracking your favorite streamers! 🔴"
        
        elif tip_type == 'frequent_user':
            checks_today = kwargs.get('checks_today', 5)
            tip_msg = "🔥 *You're active today!*\n\n"
            tip_msg += f"You've checked {checks_today}+ times today.\n\n"
            tip_msg += "💡 *Consider Premium:*\n"
            tip_msg += "  • Unlimited checks\n"
            tip_msg += "  • No daily limits\n"
            tip_msg += "  • Only ⭐150 for 7 days\n\n"
            tip_msg += "Perfect for power users like you! 💪"
        
        elif tip_type == 'inactive':
            tip_msg = "👋 *We miss you!*\n\n"
            tip_msg += "It's been a while since your last check.\n\n"
            tip_msg += "🔴 *What's new:*\n"
            tip_msg += "  • Your points have been reset\n"
            tip_msg += "  • New streamers are live\n"
            tip_msg += "  • Premium plans available\n\n"
            tip_msg += "Come back and see who's streaming! 🎉"
        
        if tip_msg:
            try:
                await helper.send_message(user_id, tip_msg, parse_mode="Markdown")
                logger.info(f"Sent contextual tip '{tip_type}' to user {user_id}")
            except Exception as e:
                logger.error(f"Failed to send tip to {user_id}: {e}")
    
    except Exception as e:
        logger.error(f"Error in send_contextual_tip: {e}", exc_info=True)
