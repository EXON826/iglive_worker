# worker/models.py

from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, Float, Boolean, Text,
    ForeignKey, event, BIGINT
)
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base

# --- SQLAlchemy Base Model ---
Base = declarative_base()

# --- Model Definitions ---

class ImageRequest(Base):
    __tablename__ = 'image_requests'
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_message_id = Column(Integer, unique=True, nullable=False)
    link_id = Column(Integer, nullable=False)

class ImageCache(Base):
    __tablename__ = 'image_cache'
    image_path = Column(Text, primary_key=True)
    imgbb_url = Column(Text, nullable=False)
    last_checked_at = Column(DateTime)

class InstaLink(Base):
    __tablename__ = 'insta_links'
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer)
    chat_id = Column(Text)
    link = Column(Text)
    timestamp = Column(DateTime, default=datetime.now)
    username = Column(Text)
    general_link = Column(Text)
    is_live = Column(Boolean, default=False)
    last_live_at = Column(DateTime)
    total_lives = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.now)
    monetized_url = Column(Text)
    monetized_at = Column(DateTime)
    status = Column(Text, default='pending')
    clicks = Column(Integer, default=0)
    earnings = Column(Float, default=0.0)
    sent = Column(Boolean, default=False)
    sent_msg_id = Column(Text)
    final_sent_msg_id = Column(Text)
    image_path = Column(Text)
    image_requested = Column(Boolean, default=False)
    image_request_sent_at = Column(DateTime)
    image_request_retries = Column(Integer, default=0)
    next_image_re_request_at = Column(DateTime)
    sent_timestamp = Column(DateTime)
    monetization_service = Column(Text, default='linkvertise')
    short_code = Column(Text)
    temp_html_path = Column(Text)
    imgbb_url = Column(Text)
    last_used_image_index = Column(Integer, default=-1)
    needs_image_request = Column(Boolean, default=False)
    sender_type = Column(String, default='telethon')

class ChatGroup(Base):
    __tablename__ = 'chat_groups'
    chat_id = Column(Text, primary_key=True)
    title = Column(String, nullable=True)
    admin_user_id = Column(BIGINT, ForeignKey('telegram_users.id'), nullable=True)
    is_active = Column(Boolean, default=False, nullable=False)

    account_id = Column(Text)
    photo_error_count = Column(Integer, default=0, nullable=False)
    is_text_only = Column(Boolean, default=False, nullable=False)
    consecutive_failures = Column(Integer, default=0, nullable=False)
    is_disabled = Column(Boolean, default=False, nullable=False)
    disabled_until = Column(DateTime)
    member_count = Column(Integer, default=0, nullable=False)

    admin_user = relationship("TelegramUser")

class TelegramUser(Base):
    __tablename__ = 'telegram_users'
    id = Column(BIGINT, primary_key=True)
    username = Column(String)
    first_name = Column(String)
    points = Column(Integer, default=10)
    last_seen = Column(DateTime, default=datetime.now)
    subscription_end = Column(DateTime, nullable=True)
    referred_by_id = Column(BIGINT, ForeignKey('telegram_users.id'), nullable=True)
    language = Column(String, default='en', nullable=False)  # Language preference
    user_bots = relationship("UserBot", back_populates="owner")
    referrals = relationship("TelegramUser", backref="referrer", remote_side=[id])

class UserActivity(Base):
    __tablename__ = 'user_activity'
    user_id = Column(BIGINT, primary_key=True, nullable=False)
    chat_id = Column(BIGINT, primary_key=True, nullable=False)
    last_message_time = Column(DateTime, default=datetime.now)
    username = Column(String)

class UserBot(Base):
    __tablename__ = 'user_bots'
    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(BIGINT, ForeignKey('telegram_users.id'))
    bot_token = Column(String, unique=True, nullable=False)
    bot_username = Column(String)
    is_active = Column(Boolean, default=True)
    owner = relationship("TelegramUser", back_populates="user_bots")

class Referral(Base):
    __tablename__ = 'referrals'
    id = Column(Integer, primary_key=True, autoincrement=True)
    referrer_id = Column(BIGINT, ForeignKey('telegram_users.id'), nullable=False)
    referred_id = Column(BIGINT, ForeignKey('telegram_users.id'), nullable=False)
    referral_code = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    points_awarded = Column(Boolean, default=False)
    referrer = relationship("TelegramUser", foreign_keys=[referrer_id])
    referred = relationship("TelegramUser", foreign_keys=[referred_id])

class PointsTransaction(Base):
    __tablename__ = 'points_transactions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BIGINT, ForeignKey('telegram_users.id'), nullable=False)
    transaction_type = Column(String, nullable=False)
    description = Column(Text)
    reference_id = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    user = relationship("TelegramUser")

class QueueItem(Base):
    __tablename__ = 'queue_items'
    id = Column(Integer, primary_key=True, autoincrement=True)
    queue_type = Column(String, nullable=False)
    payload = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    processed = Column(Boolean, default=False)
    priority = Column(Integer, default=0)


class Job(Base):
    __tablename__ = 'jobs'
    job_id = Column(Integer, primary_key=True, autoincrement=True)
    job_type = Column(String, nullable=False)
    payload = Column(Text, nullable=False)
    status = Column(String, default='pending', nullable=False)
    retries = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)