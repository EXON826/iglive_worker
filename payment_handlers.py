# payment_handlers.py
# Telegram Stars payment handlers

import os
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from models import TelegramUser, StarPayment
from telegram_helper import TelegramHelper

logger = logging.getLogger(__name__)

# Payment packages (in Telegram Stars)
PAYMENT_PACKAGES = {
    'points_50': {'stars': 50, 'points': 50, 'title': '50 Points', 'desc': 'Get 50 points instantly'},
    'points_100': {'stars': 90, 'points': 100, 'title': '100 Points', 'desc': 'Get 100 points (10% bonus)'},
    'points_500': {'stars': 400, 'points': 500, 'title': '500 Points', 'desc': 'Get 500 points (20% bonus)'},
    'premium_7d': {'stars': 150, 'days': 7, 'title': '7 Days Premium', 'desc': 'Unlimited checks for 7 days'},
    'premium_30d': {'stars': 500, 'days': 30, 'title': '30 Days Premium', 'desc': 'Unlimited checks for 30 days'},
    'premium_6m': {'stars': 2500, 'days': 180, 'title': '6 Months Premium', 'desc': 'Unlimited checks for 6 months (Save 17%)'},
    'premium_1y': {'stars': 4500, 'days': 365, 'title': '1 Year Premium', 'desc': 'Unlimited checks for 1 year (Save 25%)'},
}


async def buy_handler(session: Session, payload: dict):
    """Show payment options."""
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
        
        buy_text = "⭐ *BUY POINTS & PREMIUM*\n"
        buy_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        buy_text += "💎 *Points Packages:*\n"
        buy_text += "  • 50 Points - ⭐ 50 Stars\n"
        buy_text += "  • 100 Points - ⭐ 90 Stars (10% bonus)\n"
        buy_text += "  • 500 Points - ⭐ 400 Stars (20% bonus)\n\n"
        buy_text += "🌟 *Premium Packages:*\n"
        buy_text += "  • 7 Days - ⭐ 150 Stars\n"
        buy_text += "  • 30 Days - ⭐ 500 Stars\n"
        buy_text += "  • 6 Months - ⭐ 2,500 Stars (Save 17%)\n"
        buy_text += "  • 1 Year - ⭐ 4,500 Stars (Save 25%)\n\n"
        buy_text += "✨ Premium = Unlimited checks!\n"
        buy_text += "💳 Pay with Telegram Stars"

        buttons = {
            "inline_keyboard": [
                [{"text": "💎 50 Points (⭐ 50)", "callback_data": "pay:points_50"}],
                [{"text": "💎 100 Points (⭐ 90)", "callback_data": "pay:points_100"}],
                [{"text": "💎 500 Points (⭐ 400)", "callback_data": "pay:points_500"}],
                [{"text": "🌟 7 Days (⭐ 150)", "callback_data": "pay:premium_7d"}],
                [{"text": "🌟 30 Days (⭐ 500) 🔥 POPULAR", "callback_data": "pay:premium_30d"}],
                [{"text": "🌟 6 Months (⭐ 2,500)", "callback_data": "pay:premium_6m"}],
                [{"text": "🌟 1 Year (⭐ 4,500)", "callback_data": "pay:premium_1y"}],
                [{"text": "⬅️ Back", "callback_data": "back"}]
            ]
        }

        await helper.edit_message_text(chat_id, message_id, buy_text, parse_mode="Markdown", reply_markup=buttons)

    except Exception as e:
        logger.error(f"Error in buy_handler: {e}", exc_info=True)
        raise


async def payment_handler(session: Session, payload: dict):
    """Handle payment button clicks."""
    try:
        callback_query = payload.get('callback_query', {})
        from_user = callback_query.get('from', {})
        sender_id = from_user.get('id')
        callback_data = callback_query.get('data', '')

        if not sender_id or not callback_data.startswith('pay:'):
            return

        package_id = callback_data.split(':')[1]
        package = PAYMENT_PACKAGES.get(package_id)

        if not package:
            logger.error(f"Invalid package: {package_id}")
            return

        helper = TelegramHelper()

        # Send invoice
        invoice = await helper.send_invoice(
            chat_id=sender_id,
            title=package['title'],
            description=package['desc'],
            payload=f"{package_id}:{sender_id}",
            currency="XTR",  # Telegram Stars currency code
            prices=[{"label": package['title'], "amount": package['stars']}]
        )

        if invoice:
            logger.info(f"Invoice sent to {sender_id} for {package_id}")
        else:
            logger.error(f"Failed to send invoice to {sender_id}")

    except Exception as e:
        logger.error(f"Error in payment_handler: {e}", exc_info=True)
        raise


async def pre_checkout_handler(session: Session, payload: dict):
    """Handle pre-checkout query - MUST respond within 10 seconds."""
    helper = TelegramHelper()
    
    try:
        pre_checkout_query = payload.get('pre_checkout_query', {})
        query_id = pre_checkout_query.get('id')
        from_user = pre_checkout_query.get('from', {})
        sender_id = from_user.get('id')
        invoice_payload = pre_checkout_query.get('invoice_payload', '')

        logger.info(f"Pre-checkout query received: {query_id} from user {sender_id}")

        if not query_id:
            logger.error("No query_id in pre_checkout_query")
            return

        # Validate payment quickly
        try:
            if ':' not in invoice_payload:
                raise ValueError("Invalid payload format")
            
            package_id, user_id = invoice_payload.split(':')
            user_id = int(user_id)

            if user_id != sender_id:
                logger.error(f"User ID mismatch: {user_id} != {sender_id}")
                await helper.answer_pre_checkout_query(query_id, ok=False, error_message="User verification failed")
                return

            if package_id not in PAYMENT_PACKAGES:
                logger.error(f"Invalid package: {package_id}")
                await helper.answer_pre_checkout_query(query_id, ok=False, error_message="Invalid package")
                return

            # All checks passed - approve immediately
            await helper.answer_pre_checkout_query(query_id, ok=True)
            logger.info(f"✅ Pre-checkout APPROVED for {sender_id}, package: {package_id}")

        except ValueError as e:
            logger.error(f"Validation error: {e}")
            await helper.answer_pre_checkout_query(query_id, ok=False, error_message="Payment validation failed")
        except Exception as e:
            logger.error(f"Pre-checkout validation failed: {e}", exc_info=True)
            await helper.answer_pre_checkout_query(query_id, ok=False, error_message="Payment processing error")

    except Exception as e:
        logger.error(f"Critical error in pre_checkout_handler: {e}", exc_info=True)
        # Try to respond even on error
        if 'query_id' in locals():
            try:
                await helper.answer_pre_checkout_query(query_id, ok=False, error_message="System error")
            except:
                pass


async def successful_payment_handler(session: Session, payload: dict):
    """Handle successful payment."""
    try:
        message = payload.get('message', {})
        from_user = message.get('from', {})
        sender_id = from_user.get('id')
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
            logger.error(f"Invalid payment data for {sender_id}")
            return

        # Get user
        user = session.query(TelegramUser).filter_by(id=sender_id).first()
        if not user:
            logger.error(f"User {sender_id} not found")
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

        # Apply benefits
        if 'points' in package:
            user.points += package['points']
            success_msg = f"✅ *Payment Successful!*\n\n"
            success_msg += f"💎 +{package['points']} points added\n"
            success_msg += f"💰 New balance: {user.points} points"
        elif 'days' in package:
            if user.subscription_end and user.subscription_end > datetime.now(timezone.utc):
                user.subscription_end += timedelta(days=package['days'])
            else:
                user.subscription_end = datetime.now(timezone.utc) + timedelta(days=package['days'])
            
            success_msg = f"✅ *Payment Successful!*\n\n"
            success_msg += f"🌟 Premium activated!\n"
            success_msg += f"📅 Valid until: {user.subscription_end.strftime('%Y-%m-%d')}\n"
            success_msg += f"♾️ Unlimited checks enabled!"

        session.commit()

        # Send confirmation
        helper = TelegramHelper()
        await helper.send_message(sender_id, success_msg, parse_mode="Markdown")
        logger.info(f"Payment processed for {sender_id}: {package_id}")

    except Exception as e:
        logger.error(f"Error in successful_payment_handler: {e}", exc_info=True)
        session.rollback()
        raise
