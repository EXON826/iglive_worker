"""
Instagram web scraper - fallback if API doesn't work.
Scrapes the Instagram website directly using the browser session.
"""

import logging
import requests
import json
import re
from typing import List, Dict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class InstagramScraper:
    """Scrape Instagram web pages for live broadcasts"""
    
    def __init__(self, session_cookies: dict):
        """
        Initialize with session cookies from browser.
        
        Args:
            session_cookies: Dict of Instagram cookies (sessionid, ds_user_id, etc.)
        """
        self.cookies = session_cookies
        self.session = requests.Session()
        self.session.cookies.update(session_cookies)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'X-Requested-With': 'XMLHttpRequest',
            'X-IG-App-ID': '936619743392459',
        })
    
    def get_live_broadcasts(self) -> List[Dict]:
        """
        Scrape Instagram homepage for live broadcasts.
        
        Returns:
            List of dicts with live user information
        """
        live_users = []
        
        try:
            logger.info("Scraping Instagram homepage for lives...")
            
            # Get the main Instagram page
            response = self.session.get('https://www.instagram.com/', timeout=10)
            response.raise_for_status()
            
            # Look for embedded JSON data
            # Instagram embeds data in <script> tags
            matches = re.findall(r'window\._sharedData = ({.*?});', response.text)
            
            if matches:
                data = json.loads(matches[0])
                
                # Navigate the data structure to find broadcasts
                # This structure may change, so we try multiple paths
                entry_data = data.get('entry_data', {})
                
                # Check FeedPage
                feed_page = entry_data.get('FeedPage', [{}])[0]
                graphql = feed_page.get('graphql', {})
                user = graphql.get('user', {})
                
                # Look for broadcasts in various places
                # Method 1: Check reels tray
                if 'edge_reels_tray_to_reel' in user:
                    reels = user['edge_reels_tray_to_reel'].get('edges', [])
                    for reel in reels:
                        node = reel.get('node', {})
                        if node.get('is_live'):
                            owner = node.get('owner', {})
                            live_users.append({
                                'username': f"@{owner.get('username', 'unknown')}",
                                'broadcast_id': node.get('id', ''),
                                'viewer_count': 0,  # Not available in this data
                                'started_at': datetime.now(timezone.utc),
                                'title': '',
                                'user_id': owner.get('id')
                            })
                
                logger.info(f"Found {len(live_users)} live users via scraping")
                
            else:
                logger.warning("Could not find embedded data in Instagram page")
            
            return live_users
            
        except Exception as e:
            logger.error(f"Error scraping Instagram: {e}", exc_info=True)
            return []
    
    def get_live_from_api(self) -> List[Dict]:
        """
        Try to get lives from Instagram's internal API.
        
        Returns:
            List of dicts with live user information
        """
        live_users = []
        
        try:
            logger.info("Trying Instagram internal API for lives...")
            
            # Try the reels tray API endpoint
            response = self.session.get(
                'https://www.instagram.com/api/v1/feed/reels_tray/',
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if 'broadcasts' in data:
                    for broadcast in data['broadcasts']:
                        if broadcast.get('broadcast_status') == 'active':
                            owner = broadcast.get('broadcast_owner', {})
                            live_users.append({
                                'username': f"@{owner.get('username', 'unknown')}",
                                'broadcast_id': str(broadcast.get('id', '')),
                                'viewer_count': broadcast.get('viewer_count', 0),
                                'started_at': datetime.now(timezone.utc),
                                'title': broadcast.get('title', ''),
                                'user_id': owner.get('pk')
                            })
                
                logger.info(f"Found {len(live_users)} live users via API")
            else:
                logger.warning(f"API returned status {response.status_code}")
            
            return live_users
            
        except Exception as e:
            logger.error(f"Error calling Instagram API: {e}", exc_info=True)
            return []


def get_live_users_scraper(session_file: str = "worker/instagram_session.json") -> List[Dict]:
    """
    Get live users using web scraping.
    
    Args:
        session_file: Path to Instagram session file
        
    Returns:
        List of live users
    """
    try:
        # Load session cookies
        with open(session_file, 'r') as f:
            session_data = json.load(f)
        
        cookies = session_data.get('cookies', {})
        
        if not cookies.get('sessionid'):
            logger.error("No sessionid found in session file")
            return []
        
        # Create scraper
        scraper = InstagramScraper(cookies)
        
        # Try API first (faster)
        live_users = scraper.get_live_from_api()
        
        # If API fails, try scraping
        if not live_users:
            live_users = scraper.get_live_broadcasts()
        
        return live_users
        
    except Exception as e:
        logger.error(f"Error in scraper: {e}", exc_info=True)
        return []
