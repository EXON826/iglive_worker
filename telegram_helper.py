# worker/telegram_helper.py

import os
import logging
import httpx

logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')

class TelegramHelper:
    def __init__(self, token=None):
        self.token = token or BOT_TOKEN
        if not self.token:
            raise ValueError("Telegram Bot Token is not configured.")
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    async def send_message(self, chat_id, text, parse_mode=None, reply_markup=None):
        """Sends a text message asynchronously."""
        payload = {'chat_id': chat_id, 'text': text}
        if parse_mode:
            payload['parse_mode'] = parse_mode
        if reply_markup:
            payload['reply_markup'] = reply_markup

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(f"{self.base_url}/sendMessage", json=payload)
                response.raise_for_status()
                logger.info(f"Message sent successfully to {chat_id}")
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Error sending message to {chat_id}: {e.response.text}")
                return None
            except httpx.RequestError as e:
                logger.error(f"Network error sending message to {chat_id}: {e}")
                return None

    async def edit_message_text(self, chat_id, message_id, text, parse_mode=None, reply_markup=None):
        """Edits an existing message text."""
        payload = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': text
        }
        if parse_mode:
            payload['parse_mode'] = parse_mode
        if reply_markup:
            payload['reply_markup'] = reply_markup

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(f"{self.base_url}/editMessageText", json=payload)
                response.raise_for_status()
                logger.info(f"Message {message_id} edited successfully in chat {chat_id}")
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Error editing message {message_id} in {chat_id}: {e.response.text}")
                return None
            except httpx.RequestError as e:
                logger.error(f"Network error editing message {message_id}: {e}")
                return None

    async def answer_callback_query(self, callback_query_id, text=None, show_alert=False):
        """Answers a callback query from an inline keyboard button."""
        payload = {'callback_query_id': callback_query_id}
        if text:
            payload['text'] = text
        if show_alert:
            payload['show_alert'] = show_alert

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(f"{self.base_url}/answerCallbackQuery", json=payload)
                response.raise_for_status()
                logger.info(f"Callback query {callback_query_id} answered")
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Error answering callback query {callback_query_id}: {e.response.text}")
                return None
            except httpx.RequestError as e:
                logger.error(f"Network error answering callback query {callback_query_id}: {e}")
                return None

    async def approve_chat_join_request(self, chat_id, user_id):
        """Approves a chat join request."""
        payload = {'chat_id': chat_id, 'user_id': user_id}
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(f"{self.base_url}/approveChatJoinRequest", json=payload)
                response.raise_for_status()
                logger.info(f"Approved join request for user {user_id} in chat {chat_id}.")
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Error approving join request for user {user_id} in chat {chat_id}: {e.response.text}")
                return None
            except httpx.RequestError as e:
                logger.error(f"Network error approving join request for {user_id}: {e}")
                return None

    async def get_chat_member(self, chat_id, user_id):
        """Gets information about a member of a chat."""
        payload = {'chat_id': chat_id, 'user_id': user_id}
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(f"{self.base_url}/getChatMember", json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                # It's common for this to fail if user isn't in chat, so log as info
                logger.info(f"Could not get chat member {user_id} in {chat_id}: {e.response.text}")
                return None
            except httpx.RequestError as e:
                logger.error(f"Network error getting chat member {user_id}: {e}")
                return None

    async def is_user_admin(self, chat_id, user_id):
        """Checks if a user is an admin or creator of a chat."""
        member_info = await self.get_chat_member(chat_id, user_id)
        if member_info and member_info.get('ok'):
            status = member_info['result'].get('status')
            return status in ['creator', 'administrator']
        return False

    async def is_user_in_group(self, chat_id, user_id):
        """Checks if a user is a member or admin of a chat."""
        member_info = await self.get_chat_member(chat_id, user_id)
        if member_info and member_info.get('ok'):
            status = member_info['result'].get('status')
            # A user is considered "in" the group if they are a member, admin, or the creator.
            return status in ['creator', 'administrator', 'member']
        return False

    async def get_me(self):
        """Gets the bot's own information."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(f"{self.base_url}/getMe")
                response.raise_for_status()
                return response.json()
            except httpx.RequestError as e:
                logger.error(f"Error calling getMe: {e}")
                return None

    async def is_bot_admin(self, chat_id):
        """Checks if the bot itself is an admin in a given chat."""
        bot_info = await self.get_me()
        if bot_info and bot_info.get('ok'):
            bot_id = bot_info['result']['id']
            return await self.is_user_admin(chat_id, bot_id)
        return False
