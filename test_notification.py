#!/usr/bin/env python3
"""
Quick test script to manually create a live notification job
"""

import os
import json
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment
load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')
BOT_TOKEN = os.environ.get('BOT_TOKEN')

if not DATABASE_URL or not BOT_TOKEN:
    print("❌ Missing DATABASE_URL or BOT_TOKEN")
    exit(1)

engine = create_engine(DATABASE_URL)

# Test payload
test_payload = {
    "username": "@testuser",
    "link": "https://instagram.com/testuser",
    "last_live_at": datetime.now(timezone.utc).isoformat()
}

# Insert test job
with engine.connect() as conn:
    conn.execute(text("""
        INSERT INTO jobs (job_type, payload, status, created_at, updated_at, bot_token)
        VALUES (:job_type, :payload, :status, :created_at, :updated_at, :bot_token)
    """), {
        'job_type': 'notify_live',
        'payload': json.dumps(test_payload),
        'status': 'pending',
        'created_at': datetime.now(timezone.utc),
        'updated_at': datetime.now(timezone.utc),
        'bot_token': BOT_TOKEN
    })
    conn.commit()

print("✅ Test notification job created!")
print("Run the worker to process it: python main.py")