#!/usr/bin/env python3
"""
Database setup script for Boss Agent system.
Creates Supabase tables for memories and tasks.

Run with: python setup_db.py

SQL to run manually in Supabase SQL editor if needed:

-- memories table
CREATE TABLE IF NOT EXISTS memories (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    content TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    importance INTEGER DEFAULT 5,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- tasks table  
CREATE TABLE IF NOT EXISTS tasks (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    title TEXT NOT NULL,
    assigned_to TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'pending',
    result TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

try:
    from supabase import create_client
except ImportError:
    print("ERROR: supabase not installed. Run: pip install supabase")
    sys.exit(1)

# Get credentials
supabase_url = os.environ.get("SUPABASE_URL", "").strip()
supabase_key = os.environ.get("SUPABASE_KEY", "").strip()

if not supabase_url or not supabase_key:
    print("ERROR: SUPABASE_URL and SUPABASE_KEY not set in .env")
    sys.exit(1)

if "placeholder" in supabase_url.lower():
    print("ERROR: SUPABASE_URL still contains 'placeholder'. Please set real values in .env")
    sys.exit(1)

print(f"Connecting to Supabase at {supabase_url}...")
supabase = create_client(supabase_url, supabase_key)

# SQL statements
memories_sql = """
CREATE TABLE IF NOT EXISTS memories (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    content TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    importance INTEGER DEFAULT 5,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
"""

tasks_sql = """
CREATE TABLE IF NOT EXISTS tasks (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    title TEXT NOT NULL,
    assigned_to TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'pending',
    result TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
"""

try:
    # Execute memories table creation
    print("Creating memories table...")
    supabase.rpc("_exec_sql", {"sql": memories_sql}).execute()
    print("✓ memories table created or already exists")
except Exception as e:
    # Try direct SQL execution if rpc doesn't work
    try:
        supabase.table("memories").select("*").limit(1).execute()
        print("✓ memories table already exists")
    except:
        print(f"Note: Could not verify memories table - you may need to run the SQL manually")
        print("SQL:", memories_sql)

try:
    # Execute tasks table creation
    print("Creating tasks table...")
    supabase.rpc("_exec_sql", {"sql": tasks_sql}).execute()
    print("✓ tasks table created or already exists")
except Exception as e:
    # Try direct SQL execution if rpc doesn't work
    try:
        supabase.table("tasks").select("*").limit(1).execute()
        print("✓ tasks table already exists")
    except:
        print(f"Note: Could not verify tasks table - you may need to run the SQL manually")
        print("SQL:", tasks_sql)

print("\n✓ Database setup complete!")
print("\nIMPORTANT: If tables were not created, run this SQL manually in Supabase:")
print("\n" + memories_sql)
print(tasks_sql)
