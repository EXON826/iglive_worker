# worker/instagram_service.py

import os
import sys
import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)
# Instagram credentials from environment
IG_USERNAME = os.environ.get('IG_USERNAME')
IG_PASSWORD = os.environ.get('IG_PASSWORD')


class InstagramService:
    """
    Service for Instagram operations including login and live tracking.
    Uses instagrapi for unofficial Instagram API access.
    
    Note: This requires persistent session state, so it should run
    in a long-lived worker process (Railway/VPS), NOT in Vercel.
    """
    
    def __init__(self, username: str = None, password: str = None):
        self.username = username or IG_USERNAME
        self.password = password or IG_PASSWORD
        self.client = None
        self.is_logged_in = False
        self.session_file = "instagram_session.json"
        
        if not self.username or not self.password:
            raise ValueError("Instagram credentials not configured. Set IG_USERNAME and IG_PASSWORD environment variables.")
    
    async def login(self) -> bool:
        """
        Login to Instagram and maintain session.
        Returns True if successful, False otherwise.
        """
        try:
            # Import instagrapi here to avoid issues if not installed
            from instagrapi import Client
            from instagrapi.exceptions import ChallengeRequired, TwoFactorRequired
            
            self.client = Client()
            
            # Set custom challenge handler BEFORE any login attempts
            self.client.challenge_code_handler = self._challenge_code_handler
            
            # Stealth settings to avoid detection/bans
            self.client.delay_range = [3, 7]  # Random 3-7 second delays between requests
            
            # Set realistic device fingerprint (Samsung Galaxy S10)
            try:
                self.client.set_device({
                    "app_version": "269.0.0.18.75",
                    "android_version": 28,
                    "android_release": "9.0",
                    "dpi": "480dpi",
                    "resolution": "1080x2340",
                    "manufacturer": "Samsung",
                    "device": "SM-G973F",
                    "model": "Galaxy S10",
                    "cpu": "exynos9820",
                    "version_code": "314665256"
                })
                logger.info("Device fingerprint set to Samsung Galaxy S10")
            except Exception as e:
                logger.debug(f"Could not set device fingerprint: {e}")
            
            # Try to load existing session
            if os.path.exists(self.session_file):
                try:
                    logger.info("Attempting to load existing Instagram session...")
                    self.client.load_settings(self.session_file)
                    
                    # Verify session is valid by getting user info
                    try:
                        user_id = self.client.user_id
                        if user_id:
                            logger.info(f"Successfully loaded Instagram session. User ID: {user_id}")
                            self.is_logged_in = True
                            return True
                    except:
                        # Try to get timeline as fallback
                        self.client.get_timeline_feed()
                        logger.info("Successfully loaded Instagram session from file.")
                        self.is_logged_in = True
                        return True
                        
                except Exception as e:
                    logger.warning(f"Could not load session file: {e}. Will perform fresh login.")
                    # Don't delete the file yet, might be usable
                    pass
            
            # Fresh login
            logger.info(f"Logging into Instagram as {self.username}...")
            
            try:
                self.client.login(self.username, self.password)
                
                # Save session for future use
                self.client.dump_settings(self.session_file)
                logger.info("Instagram login successful and session saved.")
                self.is_logged_in = True
                return True
                
            except ChallengeRequired as e:
                logger.warning("Instagram requires challenge verification.")
                logger.info("Attempting to handle challenge automatically...")
                
                try:
                    # Try to solve the challenge
                    # This will prompt for verification code if needed
                    self.client.challenge_code_handler = self._challenge_code_handler
                    self.client.login(self.username, self.password)
                    
                    # Save session after successful challenge
                    self.client.dump_settings(self.session_file)
                    logger.info("Challenge completed successfully!")
                    self.is_logged_in = True
                    return True
                    
                except Exception as challenge_error:
                    logger.error(f"Challenge verification failed: {challenge_error}")
                    logger.info("\n" + "="*60)
                    logger.info("MANUAL ACTION REQUIRED:")
                    logger.info("1. Login to Instagram manually from this IP address")
                    logger.info("2. Complete any verification (email/SMS)")
                    logger.info("3. Wait 5-10 minutes")
                    logger.info("4. Try running the script again")
                    logger.info("="*60 + "\n")
                    return False
                    
            except TwoFactorRequired:
                logger.error("Two-factor authentication is enabled.")
                logger.info("Please disable 2FA or use backup codes.")
                return False
            
        except ImportError:
            logger.error("instagrapi library not installed. Run: pip install instagrapi")
            raise
        except Exception as e:
            logger.error(f"Instagram login failed: {e}", exc_info=True)
            self.is_logged_in = False
            return False
    
    def _challenge_code_handler(self, username, choice):
        """Handler for challenge verification codes"""
        logger.info(f"Challenge required for {username}. Choice: {choice}")
        logger.info("Check your email/SMS for the verification code.")
        
        # Check if running on Railway (or any non-interactive environment)
        if os.environ.get('RAILWAY_ENVIRONMENT') or not sys.stdin.isatty():
            logger.warning("=" * 60)
            logger.warning("VERIFICATION CODE NEEDED!")
            logger.warning("=" * 60)
            logger.warning(f"Instagram is asking for verification for {username}")
            logger.warning(f"Check your email/SMS for a 6-digit code")
            logger.warning("")
            logger.warning("TO SUBMIT THE CODE:")
            logger.warning("Visit: https://<your-railway-url>/submit_code?code=XXXXXX")
            logger.warning("Replace XXXXXX with your 6-digit code")
            logger.warning("")
            logger.warning("Waiting for code submission (5 minute timeout)...")
            logger.warning("=" * 60)
            
            # Import and use the web-based code handler
            try:
                from challenge_handler import wait_for_code, start_challenge_server
                
                # Start the server if not already running
                try:
                    start_challenge_server(port=int(os.environ.get('PORT', '8080')))
                except:
                    pass  # Server might already be running
                
                # Wait for code
                code = wait_for_code(timeout=300)
                if code:
                    logger.info(f"Code received: {code}")
                    return code
                else:
                    logger.error("Timeout waiting for verification code")
                    raise Exception("Verification code timeout")
            except Exception as e:
                logger.error(f"Error in web challenge handler: {e}")
                raise
        else:
            # Local/interactive mode
            code = input(f"Enter verification code: ").strip()
            return code
    
    async def get_live_users(self, usernames: List[str] = None) -> List[Dict]:
        """
        Check which users are currently live by checking the story tray.
        This is the same as the live bar you see at the top of Instagram.
        
        Args:
            usernames: Optional list of usernames to filter (not used, kept for compatibility)
            
        Returns:
            List of dicts with live user information:
            [
                {
                    'username': '@username',
                    'broadcast_id': '12345',
                    'viewer_count': 150,
                    'started_at': datetime_obj
                }
            ]
        """
        if not self.is_logged_in:
            logger.error("Not logged into Instagram. Call login() first.")
            return []
        
        live_users = []
        
        try:
            # Get timeline feed which includes live broadcasts
            logger.info("Checking for live broadcasts...")
            
            # Method 1: Try to get reels/stories feed
            try:
                # Get the user's feed which includes stories/lives
                feed = self.client.get_timeline_feed()
                
                # Check if feed has broadcast info
                if hasattr(feed, 'broadcast') and feed.broadcast:
                    broadcasts = feed.broadcast if isinstance(feed.broadcast, list) else [feed.broadcast]
                    for broadcast in broadcasts:
                        try:
                            if hasattr(broadcast, 'broadcast_status') and broadcast.broadcast_status == 'active':
                                username = broadcast.user.username if hasattr(broadcast, 'user') else 'unknown'
                                live_users.append({
                                    'username': f'@{username}',
                                    'broadcast_id': str(broadcast.id),
                                    'viewer_count': getattr(broadcast, 'viewer_count', 0),
                                    'started_at': datetime.now(timezone.utc),
                                    'title': getattr(broadcast, 'title', ''),
                                    'user_id': broadcast.user.pk if hasattr(broadcast, 'user') else None
                                })
                                logger.info(f"✅ @{username} is LIVE with {getattr(broadcast, 'viewer_count', 0)} viewers")
                        except Exception as e:
                            logger.debug(f"Error processing broadcast: {e}")
                            continue
            except Exception as e:
                logger.debug(f"Timeline feed method failed: {e}")
            
            # Method 2: Try direct API call for reels tray
            if not live_users:
                try:
                    # Use the private API endpoint directly
                    result = self.client.private_request("feed/reels_tray/")
                    
                    if result and 'broadcasts' in result:
                        for broadcast_data in result['broadcasts']:
                            try:
                                if broadcast_data.get('broadcast_status') == 'active':
                                    user_data = broadcast_data.get('broadcast_owner', {})
                                    username = user_data.get('username', 'unknown')
                                    live_users.append({
                                        'username': f'@{username}',
                                        'broadcast_id': str(broadcast_data.get('id', '')),
                                        'viewer_count': broadcast_data.get('viewer_count', 0),
                                        'started_at': datetime.now(timezone.utc),
                                        'title': broadcast_data.get('title', ''),
                                        'user_id': user_data.get('pk')
                                    })
                                    logger.info(f"✅ @{username} is LIVE with {broadcast_data.get('viewer_count', 0)} viewers")
                            except Exception as e:
                                logger.debug(f"Error processing broadcast data: {e}")
                                continue
                except Exception as e:
                    logger.debug(f"Direct API call failed: {e}")
            
            logger.info(f"Found {len(live_users)} live users")
            return live_users
            
        except Exception as e:
            logger.error(f"Error getting live users: {e}", exc_info=True)
            return []
    
    async def check_user_live(self, username: str) -> Optional[Dict]:
        """
        Check if a single user is live.
        
        Args:
            username: Instagram username
            
        Returns:
            Dict with live info if live, None otherwise
        """
        results = await self.get_live_users([username])
        return results[0] if results else None
    
    async def get_followed_accounts_live(self) -> List[Dict]:
        """
        Check which accounts the logged-in user follows are currently live.
        This is more efficient than checking individual users.
        
        Returns:
            List of dicts with live user information
        """
        if not self.is_logged_in:
            logger.error("Not logged into Instagram. Call login() first.")
            return []
        
        try:
            # Get live broadcasts from following feed
            # This is Instagram's native way of getting lives
            logger.info("Fetching live broadcasts from following feed...")
            
            # Use the reels_tray endpoint which includes live broadcasts
            broadcasts = self.client.get_reels_tray_feed()
            
            live_users = []
            if broadcasts and hasattr(broadcasts, 'broadcasts'):
                for broadcast in broadcasts.broadcasts:
                    if broadcast.broadcast_status == 'active':
                        live_users.append({
                            'username': f'@{broadcast.user.username}',
                            'broadcast_id': str(broadcast.id),
                            'viewer_count': broadcast.viewer_count or 0,
                            'started_at': datetime.now(timezone.utc),
                            'title': getattr(broadcast, 'title', '')
                        })
            
            logger.info(f"Found {len(live_users)} live users in following feed.")
            return live_users
            
        except Exception as e:
            logger.error(f"Error getting followed accounts live: {e}", exc_info=True)
            return []
    
    def logout(self):
        """Logout and cleanup."""
        if self.client:
            try:
                self.client.logout()
                logger.info("Logged out from Instagram.")
            except Exception as e:
                logger.warning(f"Error during logout: {e}")
        
        self.is_logged_in = False


# Singleton instance for worker process
_instagram_service_instance: Optional[InstagramService] = None


async def get_instagram_service() -> InstagramService:
    """
    Get or create the Instagram service singleton.
    This ensures we maintain a single logged-in session.
    """
    global _instagram_service_instance
    
    if _instagram_service_instance is None:
        logger.info("Initializing Instagram service...")
        _instagram_service_instance = InstagramService()
        await _instagram_service_instance.login()
    
    return _instagram_service_instance


async def ensure_instagram_login():
    """
    Ensure Instagram service is logged in.
    Call this periodically or at worker startup.
    """
    service = await get_instagram_service()
    if not service.is_logged_in:
        logger.warning("Instagram session lost. Re-logging in...")
        await service.login()
    return service
