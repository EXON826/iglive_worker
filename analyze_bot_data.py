import os
import sys
from sqlalchemy import create_engine, func, desc
from sqlalchemy.orm import sessionmaker
from models import Base, TelegramUser, InstaLink, Job, StarPayment, ChatGroup
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database setup
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print("Error: DATABASE_URL not found in environment variables.")
    sys.exit(1)

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

def print_header(title):
    print(f"\n{'='*50}")
    print(f" {title}")
    print(f"{'='*50}")

def analyze_users():
    print_header("USER STATISTICS")
    total_users = session.query(TelegramUser).count()
    print(f"Total Users: {total_users}")

    # Active users (last seen in 24h)
    one_day_ago = datetime.now() - timedelta(days=1)
    active_24h = session.query(TelegramUser).filter(TelegramUser.last_seen >= one_day_ago).count()
    print(f"Active Users (24h): {active_24h}")

    # Active users (last seen in 7d)
    seven_days_ago = datetime.now() - timedelta(days=7)
    active_7d = session.query(TelegramUser).filter(TelegramUser.last_seen >= seven_days_ago).count()
    print(f"Active Users (7d): {active_7d}")

    # Language distribution
    print("\nLanguage Distribution:")
    langs = session.query(TelegramUser.language, func.count(TelegramUser.id)).group_by(TelegramUser.language).all()
    for lang, count in langs:
        print(f"  - {lang}: {count}")

    # Subscriptions
    active_subs = session.query(TelegramUser).filter(TelegramUser.subscription_end > datetime.now()).count()
    print(f"\nActive Subscriptions: {active_subs}")

def analyze_engagement():
    print_header("ENGAGEMENT & CONTENT")
    total_links = session.query(InstaLink).count()
    print(f"Total Instagram Links Tracked: {total_links}")

    total_lives = session.query(func.sum(InstaLink.total_lives)).scalar() or 0
    print(f"Total Live Streams Detected: {int(total_lives)}")

    total_clicks = session.query(func.sum(InstaLink.clicks)).scalar() or 0
    print(f"Total Link Clicks: {int(total_clicks)}")

    total_earnings = session.query(func.sum(InstaLink.earnings)).scalar() or 0.0
    print(f"Total Earnings (Est.): ${total_earnings:.2f}")

    print("\nTop 5 Models by Live Count:")
    top_models = session.query(InstaLink.username, InstaLink.total_lives).order_by(desc(InstaLink.total_lives)).limit(5).all()
    for username, lives in top_models:
        print(f"  - {username}: {lives} lives")

def analyze_revenue():
    print_header("REVENUE (Star Payments)")
    total_revenue = session.query(func.sum(StarPayment.amount)).filter(StarPayment.status == 'completed').scalar() or 0
    print(f"Total Revenue: {total_revenue} Stars")

    recent_payments = session.query(StarPayment).filter(StarPayment.status == 'completed').order_by(desc(StarPayment.created_at)).limit(5).all()
    if recent_payments:
        print("\nRecent Payments:")
        for p in recent_payments:
            print(f"  - {p.amount} Stars by {p.user_id} on {p.created_at.strftime('%Y-%m-%d')}")

def analyze_system():
    print_header("SYSTEM HEALTH")
    pending_jobs = session.query(Job).filter(Job.status == 'pending').count()
    failed_jobs = session.query(Job).filter(Job.status == 'failed').count()
    print(f"Pending Jobs: {pending_jobs}")
    print(f"Failed Jobs: {failed_jobs}")

    # Jobs in last 24h
    one_day_ago = datetime.now() - timedelta(days=1)
    jobs_24h = session.query(Job).filter(Job.created_at >= one_day_ago).count()
    print(f"Jobs Processed (24h): {jobs_24h}")

if __name__ == "__main__":
    try:
        analyze_users()
        analyze_engagement()
        analyze_revenue()
        analyze_system()
    except Exception as e:
        print(f"\nError during analysis: {e}")
    finally:
        session.close()
