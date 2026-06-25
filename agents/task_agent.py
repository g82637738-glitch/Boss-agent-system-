"""
Task management agent for Boss Agent system.
Handles task creation, tracking, and status updates via Supabase.
"""

import os
import sys
from datetime import datetime
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()

try:
    from supabase import create_client, Client
except ImportError:
    print("ERROR: supabase not installed. Run: pip install supabase")
    sys.exit(1)

# Initialize Supabase client
supabase_url = os.environ.get("SUPABASE_URL", "").strip()
supabase_key = os.environ.get("SUPABASE_KEY", "").strip()

supabase_client: Optional[Client] = None
if supabase_url and supabase_key and "placeholder" not in supabase_url.lower():
    try:
        supabase_client = create_client(supabase_url, supabase_key)
    except Exception as e:
        print(f"Warning: Could not connect to Supabase: {e}")


def create_task(title: str, assigned_to: str, description: str) -> dict:
    """
    Create a new task in Supabase.
    
    Args:
        title: Short task name
        assigned_to: Agent name (e.g., "Research Agent", "Engineering Agent")
        description: Full task details
    
    Returns:
        Dictionary with task data including id
    """
    if not supabase_client:
        return {"id": "local_" + str(datetime.utcnow().timestamp()), "title": title, "assigned_to": assigned_to}
    
    try:
        task_data = {
            "title": title,
            "assigned_to": assigned_to,
            "description": description,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        result = supabase_client.table("tasks").insert(task_data).execute()
        
        if result.data:
            return result.data[0]
        return task_data
    except Exception as e:
        print(f"Error creating task: {e}")
        return {"id": "local_" + str(datetime.utcnow().timestamp()), "title": title, "assigned_to": assigned_to}


def update_task_status(task_id: str, status: str, result: str = "") -> None:
    """
    Update task status in Supabase.
    
    Args:
        task_id: UUID of the task
        status: One of "pending", "in_progress", "completed", "failed"
        result: Optional result/output of the task
    """
    if not supabase_client:
        return
    
    if status not in ("pending", "in_progress", "completed", "failed"):
        return
    
    try:
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if result:
            update_data["result"] = result
        
        supabase_client.table("tasks").update(update_data).eq("id", task_id).execute()
    except Exception as e:
        print(f"Error updating task status: {e}")


def get_all_tasks() -> list:
    """
    Get all tasks from Supabase ordered by creation date (newest first).
    
    Returns:
        List of task dictionaries
    """
    if not supabase_client:
        return []
    
    try:
        result = supabase_client.table("tasks").select("*").order(
            "created_at", desc=True
        ).execute()
        
        return result.data if result.data else []
    except Exception as e:
        print(f"Error fetching tasks: {e}")
        return []


def get_pending_tasks() -> list:
    """
    Get all pending tasks from Supabase.
    
    Returns:
        List of pending task dictionaries
    """
    if not supabase_client:
        return []
    
    try:
        result = supabase_client.table("tasks").select("*").eq(
            "status", "pending"
        ).order("created_at", desc=True).execute()
        
        return result.data if result.data else []
    except Exception as e:
        print(f"Error fetching pending tasks: {e}")
        return []
