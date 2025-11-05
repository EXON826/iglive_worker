# worker/instagram_checker.py

import os
import logging
import asyncio
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from instagram_service import ensure_instagram_login
from models import InstaLink

logger = logging.getLogger(__name__)

# How often to check for lives (in seconds) - with randomization for stealth
import random
BASE_CHECK_INTERVAL = int(os.environ.get('IG_CHECK_INTERVAL', '150'))  # Default: 150 seconds (2.5 min)
MIN_INTERVAL = 120  # Minimum 2 minutes
MAX_INTERVAL = 240  # Maximum 4 minutes

def get_random_interval():
    """Get a random check interval to appear more human-like"""
    return random.randint(MIN_INTERVAL, MAX_INTERVAL)


async def update_live_status_in_db(session_factory):
    """
    Periodically checks Instagram for live users and updates the database.
    This runs as a background task in the worker.
    """
    logger.info("Instagram live checker started.")
    
    while True:
        try:
            # Ensure we're logged in
            ig_service = await ensure_instagram_login()
            
            session = session_factory()
            try:
                logger.info("Checking story tray for live broadcasts...")
                
                # Check who's live from the story tray (people you follow)
                live_users = await ig_service.get_live_users()
                live_usernames = {user['username'].lstrip('@') for user in live_users}
                
                # Update database
                # 1. First, mark ALL users as offline
                update_all_offline = text("""
                    UPDATE insta_links
                    SET is_live = FALSE,
                        last_updated = :now
                    WHERE is_live = TRUE
                """)
                session.execute(update_all_offline, {
                    'now': datetime.now(timezone.utc)
                })
                
                # 2. Then mark/insert users who are currently live
                for user in live_users:
                    username = user['username'].lstrip('@')
                    
                    # Check if user exists in database
                    check_query = text("SELECT id FROM insta_links WHERE username = :username")
                    existing = session.execute(check_query, {'username': username}).fetchone()
                    
                    if existing:
                        # Update existing user
                        update_query = text("""
                            UPDATE insta_links
                            SET is_live = TRUE,
                                last_live_at = :now,
                                total_lives = COALESCE(total_lives, 0) + CASE WHEN is_live = FALSE THEN 1 ELSE 0 END,
                                last_updated = :now
                            WHERE username = :username
                        """)
                        session.execute(update_query, {
                            'username': username,
                            'now': datetime.now(timezone.utc)
                        })
                        logger.info(f"✅ @{username} is LIVE! (Viewers: {user['viewer_count']})")
                    else:
                        # Insert new user
                        insert_query = text("""
                            INSERT INTO insta_links (username, is_live, last_live_at, total_lives, last_updated, link)
                            VALUES (:username, TRUE, :now, 1, :now, :link)
                        """)
                        session.execute(insert_query, {
                            'username': username,
                            'now': datetime.now(timezone.utc),
                            'link': f'https://instagram.com/{username}'
                        })
                        logger.info(f"✅ NEW USER @{username} is LIVE! (Viewers: {user['viewer_count']})")
                
                session.commit()
                logger.info(f"Live status check complete. {len(live_users)} user(s) are live.")
                
            except Exception as e:
                logger.error(f"Error updating live status: {e}", exc_info=True)
                session.rollback()
            finally:
                session.close()
            
            # Wait before next check with random interval for stealth
            next_interval = get_random_interval()
            logger.info(f"Next check in {next_interval} seconds ({next_interval/60:.1f} minutes)")
            await asyncio.sleep(next_interval)
            
        except Exception as e:
            logger.error(f"Critical error in Instagram checker loop: {e}", exc_info=True)
            # On error, wait 3x longer before retrying (exponential backoff)
            error_wait = get_random_interval() * 3
            logger.warning(f"Waiting {error_wait} seconds before retry due to error")
            await asyncio.sleep(error_wait)


async def get_currently_live_users(session):
    """
    Get list of currently live Instagram users from database.
    
    Args:
        session: SQLAlchemy session
        
    Returns:
        List of dicts with user info
    """
    try:
        query = text("""
            SELECT username, last_live_at, total_lives, link
            FROM insta_links
            WHERE is_live = TRUE
            ORDER BY last_live_at DESC
        """)
        result = session.execute(query).fetchall()
        
        live_users = []
        for row in result:
            live_users.append({
                'username': row[0],
                'last_live_at': row[1],
                'total_lives': row[2],
                'link': row[3]
            })
        
        return live_users
        
    except Exception as e:
        logger.error(f"Error fetching live users from DB: {e}", exc_info=True)
        return []


def start_instagram_checker(session_factory):
    """
    Start the Instagram checker as a background task.
    Call this from the worker main loop.
    Returns the coroutine function itself.
    """
    async def run_checker():
        await update_live_status_in_db(session_factory)
    
    return run_checker


if __name__ == '__main__':
    # For testing purposes
    logging.basicConfig(level=logging.INFO)
    
    load_dotenv()
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL not set")
    
    engine = create_engine(DATABASE_URL)
    SessionFactory = sessionmaker(bind=engine)
    
    asyncio.run(update_live_status_in_db(SessionFactory))
