"""
Supabase database client and helpers for TikTok video research.
"""

import os
import re
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in .env")


def get_client() -> Client:
    """Get Supabase client instance."""
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def extract_video_id(url: str) -> Optional[str]:
    """
    Extract TikTok video ID from URL.

    Examples:
        https://www.tiktok.com/@user/video/7572353159671188791 -> 7572353159671188791
        https://www.tiktok.com/@user/video/7572353159671188791?q=tokyo -> 7572353159671188791
    """
    match = re.search(r'/video/(\d+)', url)
    return match.group(1) if match else None


def extract_author(url: str) -> Optional[str]:
    """
    Extract author username from URL.

    Example:
        https://www.tiktok.com/@jacksdiningroom/video/123 -> jacksdiningroom
    """
    match = re.search(r'@([^/]+)', url)
    return match.group(1) if match else None


def video_exists(video_id: str) -> bool:
    """Check if a video already exists in the database."""
    client = get_client()
    result = client.table("videos").select("id").eq("video_id", video_id).execute()
    return len(result.data) > 0


def get_all_video_ids() -> set[str]:
    """Get all video IDs from the database (for batch duplicate checking)."""
    client = get_client()
    result = client.table("videos").select("video_id").execute()
    return {row["video_id"] for row in result.data if row.get("video_id")}


def insert_video(
    video_id: str,
    url: str,
    author: Optional[str] = None,
    title: Optional[str] = None,
    duration_sec: Optional[float] = None,
    transcript: Optional[str] = None,
    ocr_text: Optional[str] = None,
    gcs_prefix: Optional[str] = None,
    frame_count: Optional[int] = None,
    processed_at: Optional[datetime] = None,
) -> dict:
    """
    Insert a new video record into the database.

    Returns the inserted record.
    """
    client = get_client()

    data = {
        "video_id": video_id,
        "url": url,
        "author": author or extract_author(url),
        "title": title,
        "duration_sec": duration_sec,
        "transcript": transcript,
        "ocr_text": ocr_text,
        "gcs_prefix": gcs_prefix,
        "frame_count": frame_count,
        "processed_at": processed_at.isoformat() if processed_at else None,
    }

    # Remove None values
    data = {k: v for k, v in data.items() if v is not None}

    result = client.table("videos").insert(data).execute()
    return result.data[0] if result.data else {}


def get_video(video_id: str) -> Optional[dict]:
    """Get a video record by video_id."""
    client = get_client()
    result = client.table("videos").select("*").eq("video_id", video_id).execute()
    return result.data[0] if result.data else None


def search_videos(query: str, limit: int = 10) -> list[dict]:
    """
    Full-text search across transcripts and OCR text.

    Uses PostgreSQL's to_tsvector for text search.
    """
    client = get_client()

    # Use textSearch for full-text search
    result = client.table("videos").select("*").or_(
        f"transcript.ilike.%{query}%,ocr_text.ilike.%{query}%"
    ).limit(limit).execute()

    return result.data


def list_videos(limit: int = 50, offset: int = 0) -> list[dict]:
    """List all videos, ordered by upload date."""
    client = get_client()
    result = (
        client.table("videos")
        .select("*")
        .order("uploaded_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return result.data


def get_stats() -> dict:
    """Get database statistics."""
    client = get_client()
    result = client.table("videos").select("id", count="exact").execute()
    return {
        "total_videos": result.count,
    }


if __name__ == "__main__":
    # Test connection
    print("Testing Supabase connection...")
    stats = get_stats()
    print(f"Connected! Total videos in database: {stats['total_videos']}")
