import time
import logging
from collections import defaultdict, deque
from config import RATE_LIMITS

logger = logging.getLogger(__name__)

class RateLimiter:
    """Fixed rate limiter with memory cleanup"""
    
    def __init__(self):
        self.user_actions = defaultdict(deque)
        self.limits = RATE_LIMITS
        self.last_cleanup = time.time()
    
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
            return False
        
        # Record this action
        user_queue.append(now)
        
        # Periodic cleanup
        self.cleanup_old_data()
        
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
    
    def cleanup_old_data(self):
        """Clean up old user action data to prevent memory leaks"""
        now = time.time()
        # Only cleanup every 10 minutes
        if now - self.last_cleanup < 600:
            return
        
        keys_to_remove = []
        for key, queue in self.user_actions.items():
            # Remove entries older than 1 hour
            while queue and queue[0] <= now - 3600:
                queue.popleft()
            # If queue is empty, mark key for removal
            if not queue:
                keys_to_remove.append(key)
        
        # Remove empty queues
        for key in keys_to_remove:
            del self.user_actions[key]
        
        self.last_cleanup = now
        if keys_to_remove:
            logger.info(f"Cleaned up {len(keys_to_remove)} empty rate limit queues")

# Global rate limiter instance
rate_limiter = RateLimiter()