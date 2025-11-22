# config.py
# Configuration constants to replace hardcoded values

import os

# Bot configuration
BOT_USERNAME = os.environ.get('BOT_USERNAME', 'IGLiveZBot')
BOT_TOKEN = os.environ.get('BOT_TOKEN')
BOT_API_ID = os.environ.get('BOT_API_ID')
BOT_API_HASH = os.environ.get('BOT_API_HASH')

# Group configuration
REQUIRED_GROUP_URL = os.environ.get('REQUIRED_GROUP_URL', "https://t.me/+FBDgBcLD1C5jN2Jk")
REQUIRED_GROUP_ID = int(os.environ.get('REQUIRED_GROUP_ID', -1002891494486))
REQUIRE_GROUP_MEMBERSHIP = os.environ.get('REQUIRE_GROUP_MEMBERSHIP', 'false').lower() == 'true'

# Pagination configuration
LIVE_STREAMS_PER_PAGE = int(os.environ.get('LIVE_STREAMS_PER_PAGE', 5))

# Premium configuration
PREMIUM_VALIDITY_DAYS = int(os.environ.get('PREMIUM_VALIDITY_DAYS', 30))

# Rate limiting configuration
RATE_LIMITS = {
    'check_live': (5, 60),           # 5 checks per minute
    'live_check_logic': (10, 60),    # 10 live check operations per minute
    'button_click': (20, 60),        # 20 button clicks per minute
    'payment': (3, 300),             # 3 payment attempts per 5 minutes
    'message': (10, 60),             # 10 messages per minute
}

# Points configuration
DEFAULT_DAILY_POINTS = int(os.environ.get('DEFAULT_DAILY_POINTS', 3))
REFERRAL_BONUS_POINTS = int(os.environ.get('REFERRAL_BONUS_POINTS', 5))
FREE_PREMIUM_REFERRAL_THRESHOLD = int(os.environ.get('FREE_PREMIUM_REFERRAL_THRESHOLD', 30))

# Admin configuration
ADMIN_IDS_STR = os.environ.get('ADMIN_IDS', '')
ADMIN_IDS = [int(id.strip()) for id in ADMIN_IDS_STR.split(',') if id.strip().isdigit()]

# Auto-Broadcast configuration
AUTO_BROADCAST_THRESHOLD = int(os.environ.get('AUTO_BROADCAST_THRESHOLD', 10))
AUTO_BROADCAST_COOLDOWN_HOURS = int(os.environ.get('AUTO_BROADCAST_COOLDOWN_HOURS', 24))