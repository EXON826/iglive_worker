# Production-ready configuration with validation
import os
import logging

logger = logging.getLogger(__name__)

def safe_int(value: str, default: int, name: str) -> int:
    """Safely convert string to int with validation"""
    try:
        result = int(value)
        if result < 0:
            logger.warning(f"Config {name} is negative ({result}), using default ({default})")
            return default
        return result
    except (ValueError, TypeError):
        logger.warning(f"Invalid config {name} ({value}), using default ({default})")
        return default

def safe_bool(value: str, default: bool) -> bool:
    """Safely convert string to bool"""
    if isinstance(value, bool):
        return value
    return str(value).lower() in ('true', '1', 'yes', 'on')

# Bot configuration with validation
BOT_USERNAME = os.environ.get('BOT_USERNAME', 'IGLiveZBot')
BOT_TOKEN = os.environ.get('BOT_TOKEN')
BOT_API_ID = os.environ.get('BOT_API_ID')
BOT_API_HASH = os.environ.get('BOT_API_HASH')

# Validate critical config
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

# Group configuration
REQUIRED_GROUP_URL = os.environ.get('REQUIRED_GROUP_URL', "https://t.me/+FBDgBcLD1C5jN2Jk")
REQUIRED_GROUP_ID = safe_int(os.environ.get('REQUIRED_GROUP_ID', '-1002891494486'), -1002891494486, 'REQUIRED_GROUP_ID')
REQUIRE_GROUP_MEMBERSHIP = safe_bool(os.environ.get('REQUIRE_GROUP_MEMBERSHIP', 'false'), False)

# Pagination configuration
LIVE_STREAMS_PER_PAGE = safe_int(os.environ.get('LIVE_STREAMS_PER_PAGE', '5'), 5, 'LIVE_STREAMS_PER_PAGE')
LIVE_STREAMS_PER_PAGE = max(1, min(LIVE_STREAMS_PER_PAGE, 20))  # Clamp between 1-20

# Premium configuration
PREMIUM_VALIDITY_DAYS = safe_int(os.environ.get('PREMIUM_VALIDITY_DAYS', '30'), 30, 'PREMIUM_VALIDITY_DAYS')
PREMIUM_VALIDITY_DAYS = max(1, min(PREMIUM_VALIDITY_DAYS, 365))  # Clamp between 1-365 days

# Points configuration
DEFAULT_DAILY_POINTS = safe_int(os.environ.get('DEFAULT_DAILY_POINTS', '3'), 3, 'DEFAULT_DAILY_POINTS')
DEFAULT_DAILY_POINTS = max(1, min(DEFAULT_DAILY_POINTS, 100))  # Clamp between 1-100

REFERRAL_BONUS_POINTS = safe_int(os.environ.get('REFERRAL_BONUS_POINTS', '5'), 5, 'REFERRAL_BONUS_POINTS')
REFERRAL_BONUS_POINTS = max(1, min(REFERRAL_BONUS_POINTS, 50))  # Clamp between 1-50

FREE_PREMIUM_REFERRAL_THRESHOLD = safe_int(os.environ.get('FREE_PREMIUM_REFERRAL_THRESHOLD', '30'), 30, 'FREE_PREMIUM_REFERRAL_THRESHOLD')
FREE_PREMIUM_REFERRAL_THRESHOLD = max(1, min(FREE_PREMIUM_REFERRAL_THRESHOLD, 1000))  # Clamp between 1-1000

# Rate limiting configuration with validation
RATE_LIMITS = {
    'check_live': (
        safe_int(os.environ.get('RATE_LIMIT_CHECK_LIVE_COUNT', '5'), 5, 'RATE_LIMIT_CHECK_LIVE_COUNT'),
        safe_int(os.environ.get('RATE_LIMIT_CHECK_LIVE_WINDOW', '60'), 60, 'RATE_LIMIT_CHECK_LIVE_WINDOW')
    ),
    'live_check_logic': (
        safe_int(os.environ.get('RATE_LIMIT_LIVE_LOGIC_COUNT', '10'), 10, 'RATE_LIMIT_LIVE_LOGIC_COUNT'),
        safe_int(os.environ.get('RATE_LIMIT_LIVE_LOGIC_WINDOW', '60'), 60, 'RATE_LIMIT_LIVE_LOGIC_WINDOW')
    ),
    'button_click': (
        safe_int(os.environ.get('RATE_LIMIT_BUTTON_COUNT', '20'), 20, 'RATE_LIMIT_BUTTON_COUNT'),
        safe_int(os.environ.get('RATE_LIMIT_BUTTON_WINDOW', '60'), 60, 'RATE_LIMIT_BUTTON_WINDOW')
    ),
    'payment': (
        safe_int(os.environ.get('RATE_LIMIT_PAYMENT_COUNT', '3'), 3, 'RATE_LIMIT_PAYMENT_COUNT'),
        safe_int(os.environ.get('RATE_LIMIT_PAYMENT_WINDOW', '300'), 300, 'RATE_LIMIT_PAYMENT_WINDOW')
    ),
    'message': (
        safe_int(os.environ.get('RATE_LIMIT_MESSAGE_COUNT', '10'), 10, 'RATE_LIMIT_MESSAGE_COUNT'),
        safe_int(os.environ.get('RATE_LIMIT_MESSAGE_WINDOW', '60'), 60, 'RATE_LIMIT_MESSAGE_WINDOW')
    ),
}

# Validate rate limits
for action, (count, window) in RATE_LIMITS.items():
    if count <= 0 or window <= 0:
        logger.error(f"Invalid rate limit for {action}: count={count}, window={window}")
        RATE_LIMITS[action] = (5, 60)  # Safe defaults

# Log configuration on startup
logger.info(f"Configuration loaded: PREMIUM_VALIDITY_DAYS={PREMIUM_VALIDITY_DAYS}, "
           f"DEFAULT_DAILY_POINTS={DEFAULT_DAILY_POINTS}, "
           f"LIVE_STREAMS_PER_PAGE={LIVE_STREAMS_PER_PAGE}")