import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

from models import TelegramUser, StarPayment
from telegram_helper import TelegramHelper
from rate_limiter import rate_limiter
from config import PREMIUM_VALIDITY_DAYS

logger = logging.getLogger(__name__)

PAYMENT_PACKAGES = {
    'premium_7d': {'stars': 150, 'days': 7, 'title': '7 Days Premium'},
    'premium_30d': {'stars': 500, 'days': 30, 'title': '30 Days Premium'},
}

def check_premium_status(session: Session, user_id: int) -> bool:
    """Check if user has active premium subscription"""
    premium_check = session.execute(text("""
        SELECT COUNT(*) FROM star_payments 
        WHERE user_id = :user_id 
        AND package_type LIKE 'premium_%' 
        AND status = 'completed'
        AND completed_at > NOW() - INTERVAL :days DAY
    """), {'user_id': user_id, 'days': PREMIUM_VALIDITY_DAYS}).scalar()
    return premium_check > 0

async def buy_handler(session: Session, payload: dict):
    """Fixed buy handler with proper premium detection"""
    try:
        callback_query = payload.get('callback_query', {})
        sender_id = callback_query.get('from', {}).get('id')
        message = callback_query.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        message_id = message.get('message_id')

        if not sender_id:
            return

        helper = TelegramHelper()
        user = session.query(TelegramUser).filter_by(id=sender_id).first()
        is_premium = check_premium_status(session, user.id) if user else False
        
        buy_text = "🔄 *RENEW PREMIUM*\n" if is_premium else "⭐ *BUY PREMIUM*\n"
        buy_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        buy_text += "🌟 *Premium Packages:*\n"
        buy_text += "  • 7 Days - ⭐ 150 Stars\n"
        buy_text += "  • 30 Days - ⭐ 500 Stars\n\n"
        buy_text += "✨ *Premium Benefits:*\n"
        buy_text += "  ✅ Unlimited checks 24/7\n"
        buy_text += "  🔔 Live notifications\n"
        buy_text += "  ⚡ No daily limits"

        buttons = {"inline_keyboard": [
            [{"text": "🌟 7 Days - ⭐ 150", "callback_data": "pay:premium_7d"}],
            [{"text": "🌟 30 Days - ⭐ 500", "callback_data": "pay:premium_30d"}],
            [{"text": "⬅️ Back", "callback_data": "back"}]
        ]}

        try:
            await helper.edit_message_text(chat_id, message_id, buy_text, parse_mode="Markdown", reply_markup=buttons)
        except:
            await helper.send_message(sender_id, buy_text, parse_mode="Markdown", reply_markup=buttons)

    except Exception as e:
        logger.error(f"Error in buy_handler: {e}")

async def successful_payment_handler(session: Session, payload: dict):
    """Fixed payment handler with proper transaction handling"""
    try:
        message = payload.get('message', {})
        sender_id = message.get('from', {}).get('id')
        successful_payment = message.get('successful_payment', {})

        if not sender_id or not successful_payment:
            return

        invoice_payload = successful_payment.get('invoice_payload', '')
        telegram_payment_charge_id = successful_payment.get('telegram_payment_charge_id')
        total_amount = successful_payment.get('total_amount', 0)

        # Parse package info
        package_id, user_id = invoice_payload.split(':')
        user_id = int(user_id)
        package = PAYMENT_PACKAGES.get(package_id)

        if not package or user_id != sender_id:
            return

        user = session.query(TelegramUser).filter_by(id=sender_id).first()
        if not user:
            return

        # Record payment
        payment = StarPayment(
            user_id=sender_id,
            telegram_payment_charge_id=telegram_payment_charge_id,
            amount=total_amount,
            package_type=package_id,
            status='completed',
            completed_at=datetime.now(timezone.utc)
        )
        session.add(payment)
        session.commit()

        success_msg = f"✅ *Payment Successful!*\n\n"
        success_msg += f"🌟 Premium activated!\n"
        success_msg += f"📅 Valid for {package['days']} days\n"
        success_msg += f"♾️ Unlimited checks enabled!"

        helper = TelegramHelper()
        try:
            await helper.send_message(sender_id, success_msg, parse_mode="Markdown")
        except:
            await helper.send_message(sender_id, "Payment successful! Premium activated.")

    except Exception as e:
        logger.error(f"Error in successful_payment_handler: {e}")
        session.rollback()