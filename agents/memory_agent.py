"""
Persistent memory agent for Boss Agent system.
Handles working, episodic, and semantic memory via Supabase.
"""

import os
import sys
from datetime import datetime, timedelta
import json
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

try:
    from supabase import create_client, Client
except ImportError:
    print("ERROR: supabase not installed. Run: pip install supabase")
    sys.exit(1)

try:
    import groq
except ImportError:
    print("ERROR: groq not installed")
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

# Initialize Groq client for consolidation
groq_api_key = os.environ.get("GROQ_API_KEY")
groq_client = None
if groq_api_key and groq_api_key != "PLACEHOLDER":
    try:
        groq_client = groq.Groq(api_key=groq_api_key)
    except Exception as e:
        print(f"Warning: Could not initialize Groq client: {e}")


def save_memory(content: str, memory_type: str) -> None:
    """
    Save a memory to Supabase.
    
    Args:
        content: The memory content
        memory_type: One of "working", "episodic", "semantic"
    """
    if not supabase_client:
        return
    
    if memory_type not in ("working", "episodic", "semantic"):
        return
    
    try:
        memory_data = {
            "content": content,
            "memory_type": memory_type,
            "importance": 5
        }
        supabase_client.table("memories").insert(memory_data).execute()
    except Exception as e:
        print(f"Error saving memory: {e}")


def get_relevant_memories(query: str, limit: int = 5) -> list:
    """
    Fetch relevant memories from Supabase.
    
    Args:
        query: Search query (used for context, exact match not implemented)
        limit: Maximum number of memories to return
    
    Returns:
        List of memory content strings
    """
    if not supabase_client:
        return []
    
    try:
        # Fetch last `limit` memories ordered by created_at descending
        result = supabase_client.table("memories").select("content").order(
            "created_at", desc=True
        ).limit(limit).execute()
        
        memories = [item["content"] for item in result.data] if result.data else []
        return memories
    except Exception as e:
        print(f"Error fetching memories: {e}")
        return []


def consolidate_memories() -> None:
    """
    Consolidate old episodic memories into semantic memories.
    Fetches episodic memories older than 24 hours, summarizes them,
    saves as semantic memory, and deletes the old records.
    """
    if not supabase_client or not groq_client:
        return
    
    try:
        # Calculate cutoff time (24 hours ago)
        cutoff_time = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        
        # Fetch episodic memories older than 24 hours
        result = supabase_client.table("memories").select(
            "id, content"
        ).eq("memory_type", "episodic").lt("created_at", cutoff_time).execute()
        
        if not result.data or len(result.data) == 0:
            return
        
        # Combine memories into a single string
        episodic_content = "\n".join([m["content"] for m in result.data])
        memory_ids = [m["id"] for m in result.data]
        
        # Send to Groq for summarization
        try:
            response = groq_client.chat.completions.create(
                model="mixtral-8x7b-32768",
                messages=[
                    {
                        "role": "system",
                        "content": "Summarize these past events into key facts only. Plain sentences, no formatting."
                    },
                    {
                        "role": "user",
                        "content": episodic_content
                    }
                ],
                temperature=0.5,
                max_tokens=500
            )
            
            summary = response.choices[0].message.content if response.choices else ""
            
            if summary:
                # Save summary as semantic memory
                save_memory(summary, "semantic")
                
                # Delete old episodic memories
                for memory_id in memory_ids:
                    supabase_client.table("memories").delete().eq("id", memory_id).execute()
                
                print(f"Consolidated {len(memory_ids)} episodic memories into semantic memory")
        
        except Exception as e:
            print(f"Error during Groq consolidation: {e}")
    
    except Exception as e:
        print(f"Error consolidating memories: {e}")
