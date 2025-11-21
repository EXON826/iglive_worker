#!/usr/bin/env python3
"""
Quick script to fetch current Supabase schema
Run: python fetch_schema.py
"""

import os
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

def fetch_schema():
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Get table info
    query = """
    SELECT table_name, column_name, data_type, is_nullable
    FROM information_schema.columns 
    WHERE table_schema = 'public'
    AND table_name IN ('insta_links', 'chat_groups', 'telegram_users', 'jobs')
    ORDER BY table_name, ordinal_position;
    """
    
    result = supabase.rpc('exec_sql', {'sql': query}).execute()
    print("Current Schema:")
    for row in result.data:
        print(f"{row['table_name']}.{row['column_name']} - {row['data_type']}")

if __name__ == "__main__":
    fetch_schema()