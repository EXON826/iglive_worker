import time
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class RateLimiter:
    """Simple in-memory rate limiter for user actions"""
    
    def __init__(self):
        # Store user action timestamps
        self.user_actions = defaultdict(deque)
        # Rate limits: action_type -> (max_requests, time_window_seconds)
        self.limits = {
            'check_live': (5, 60),      # 5 checks per minute
            'button_click': (20, 60),   # 20 button clicks per minute
            'payment': (3, 300),        # 3 payment attempts per 5 minutes
            'message': (10, 60),        # 10 messages per minute
        }
    
    def is_allowed(self, user_id: int, action_type: str) -> bool:
        """Check if user action is within rate limits"""
        if action_type not in self.limits:
            return True
        
        max_requests, window = self.limits[action_type]
        now = time.time()
        key = f"{user_id}:{action_type}"
        
        # Clean old entries
        user_queue = self.user_actions[key]
        while user_queue and user_queue[0] <= now - window:
            user_queue.popleft()
        
        # Check if under limit
        if len(user_queue) >= max_requests:
            logger.warning(f"Rate limit exceeded for user {user_id}, action: {action_type}")
            return False
        
        # Record this action
        user_queue.append(now)
        return True
    
    def get_reset_time(self, user_id: int, action_type: str) -> int:
        """Get seconds until rate limit resets"""
        if action_type not in self.limits:
            return 0
        
        window = self.limits[action_type][1]
        key = f"{user_id}:{action_type}"
        user_queue = self.user_actions[key]
        
        if not user_queue:
            return 0
        
        oldest_action = user_queue[0]
        reset_time = oldest_action + window - time.time()
        return max(0, int(reset_time))

# Global rate limiter instance
rate_limiter = RateLimiter()