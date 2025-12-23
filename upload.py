#!/usr/bin/env python3
"""
Upload processed TikTok videos to Google Cloud Storage and Supabase.

Scans the output/ directory for processed videos and uploads:
- metadata.json
- transcript.txt
- ocr_summary.txt
- transcript_timestamps.json
- frames/ (max 20 key frames selected by smart algorithm)

Smart frame selection prioritizes:
1. Frames where on-screen text changes (OCR-based)
2. Frames at speech segment boundaries (timestamp-based)
3. Every Nth frame as fallback

Usage:
    python upload.py              # Upload and delete local files
    python upload.py --dry-run    # Preview what would happen
    python upload.py --keep       # Upload but keep local files
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google.cloud import storage

import db

# Load environment variables
load_dotenv()

GCS_BUCKET = os.getenv("GCS_BUCKET", "tiktok-research-rhu")


def get_gcs_client() -> storage.Client:
    """Get Google Cloud Storage client."""
    return storage.Client()


def find_processed_videos(output_dir: Path) -> list[Path]:
    """
    Find all processed video directories in output/.

    A valid processed directory contains at least metadata.json or transcript.txt.
    """
    videos = []
    for item in output_dir.iterdir():
        if item.is_dir():
            # Check for expected files
            has_metadata = (item / "metadata.json").exists()
            has_transcript = (item / "transcript.txt").exists()
            if has_metadata or has_transcript:
                videos.append(item)
    return sorted(videos)


def extract_video_info(video_dir: Path) -> dict:
    """Extract video information from the processed directory."""
    info = {
        "dir_name": video_dir.name,
        "url": None,
        "video_id": None,
        "author": None,
        "title": None,
        "duration_sec": None,
        "transcript": None,
        "ocr_text": None,
        "frame_count": 0,
    }

    # Read metadata.json
    metadata_path = video_dir / "metadata.json"
    if metadata_path.exists():
        try:
            with open(metadata_path) as f:
                metadata = json.load(f)
                info["url"] = metadata.get("url")
                info["video_id"] = metadata.get("video_id") or db.extract_video_id(info["url"] or "")
                info["author"] = metadata.get("author") or db.extract_author(info["url"] or "")
                info["title"] = metadata.get("title")
                info["duration_sec"] = metadata.get("duration")
        except json.JSONDecodeError:
            pass

    # Read transcript
    transcript_path = video_dir / "transcript.txt"
    if transcript_path.exists():
        info["transcript"] = transcript_path.read_text().strip()

    # Read OCR summary
    ocr_summary_path = video_dir / "ocr_summary.txt"
    if ocr_summary_path.exists():
        info["ocr_text"] = ocr_summary_path.read_text().strip()

    # Count frames
    frames_dir = video_dir / "frames"
    if frames_dir.exists():
        info["frame_count"] = len(list(frames_dir.glob("*.jpg")))

    return info


def select_key_frames(video_dir: Path, fallback_interval: int = 10, max_frames: int = 20) -> list[Path]:
    """
    Select key frames based on content changes.

    Priority:
    1. OCR-based: frames where on-screen text changes
    2. Timestamp-based: frames at speech segment boundaries
    3. Interval-based: every Nth frame as fallback

    Args:
        max_frames: Maximum number of frames to return (default: 20)
    """
    frames_dir = video_dir / "frames"
    if not frames_dir.exists():
        return []

    frame_files = sorted(frames_dir.glob("*.jpg"))
    if not frame_files:
        return []

    selected_frames = set()

    # Method 1: OCR-based selection (frames where text changes)
    ocr_path = video_dir / "ocr.json"
    if ocr_path.exists():
        try:
            with open(ocr_path) as f:
                ocr_data = json.load(f)

            prev_text = None
            for frame_name, text in ocr_data.items():
                # Skip empty/boilerplate text
                if not text or text.lower().startswith("no text"):
                    continue

                # Normalize text for comparison
                normalized = text.strip().lower()[:100]

                # Select frame if text is new/different
                if normalized != prev_text:
                    frame_path = frames_dir / frame_name
                    if frame_path.exists():
                        selected_frames.add(frame_path)
                    prev_text = normalized

        except (json.JSONDecodeError, KeyError):
            pass

    # Method 2: Timestamp-based selection (speech segment boundaries)
    timestamps_path = video_dir / "transcript_timestamps.json"
    if timestamps_path.exists() and len(selected_frames) < 3:
        try:
            with open(timestamps_path) as f:
                segments = json.load(f)

            # Get video duration from metadata or estimate from frames
            fps = 1  # Our extraction is ~1 fps
            total_frames = len(frame_files)

            for seg in segments:
                # Select frame at start of each speech segment
                frame_num = int(seg["start"] * fps) + 1
                if 1 <= frame_num <= total_frames:
                    frame_name = f"frame_{frame_num:03d}.jpg"
                    frame_path = frames_dir / frame_name
                    if frame_path.exists():
                        selected_frames.add(frame_path)

        except (json.JSONDecodeError, KeyError):
            pass

    # Method 3: Fallback to interval-based if we have too few frames
    if len(selected_frames) < 3:
        for i, frame_path in enumerate(frame_files):
            if i % fallback_interval == 0:
                selected_frames.add(frame_path)

    # Always include first and last frame
    if frame_files:
        selected_frames.add(frame_files[0])
        selected_frames.add(frame_files[-1])

    # Sort and limit to max_frames (evenly distributed if over limit)
    sorted_frames = sorted(selected_frames)

    if len(sorted_frames) > max_frames:
        # Evenly sample to stay under limit
        # This creates exactly max_frames indices evenly spread from 0 to len-1
        step = (len(sorted_frames) - 1) / (max_frames - 1)
        indices = [int(i * step) for i in range(max_frames)]
        sorted_frames = [sorted_frames[i] for i in indices]

    return sorted_frames


def upload_to_gcs(
    video_dir: Path,
    video_id: str,
    frame_interval: int = 10,
    dry_run: bool = False,
) -> tuple[str, int]:
    """
    Upload video artifacts to GCS.

    Returns (gcs_prefix, frames_uploaded).
    """
    client = get_gcs_client()
    bucket = client.bucket(GCS_BUCKET)
    gcs_prefix = f"videos/{video_id}/"

    files_to_upload = []

    # Always upload these text files
    for filename in ["metadata.json", "transcript.txt", "ocr_summary.txt", "transcript_timestamps.json"]:
        local_path = video_dir / filename
        if local_path.exists():
            files_to_upload.append((local_path, f"{gcs_prefix}{filename}"))

    # Select key frames intelligently
    key_frames = select_key_frames(video_dir, fallback_interval=frame_interval)
    frames_uploaded = 0

    for frame_path in key_frames:
        gcs_path = f"{gcs_prefix}frames/{frame_path.name}"
        files_to_upload.append((frame_path, gcs_path))
        frames_uploaded += 1

    # Upload files
    for local_path, gcs_path in files_to_upload:
        if dry_run:
            print(f"  [DRY RUN] Would upload: {local_path.name} -> gs://{GCS_BUCKET}/{gcs_path}")
        else:
            blob = bucket.blob(gcs_path)
            blob.upload_from_filename(str(local_path))
            print(f"  Uploaded: {local_path.name}")

    return gcs_prefix, frames_uploaded


def delete_video_dir(video_dir: Path, dry_run: bool = False) -> float:
    """
    Delete a video directory and all its contents.

    Returns the size in MB that was freed (or would be freed in dry run).
    Returns 0 if deletion failed.
    """
    try:
        size_mb = sum(f.stat().st_size for f in video_dir.rglob("*") if f.is_file()) / (1024 * 1024)
    except Exception:
        size_mb = 0

    if dry_run:
        print(f"  [DRY RUN] Would delete: {video_dir.name} ({size_mb:.1f} MB)")
        return size_mb

    try:
        shutil.rmtree(video_dir)
        print(f"  Cleaned up: {video_dir.name} ({size_mb:.1f} MB freed)")
        return size_mb
    except Exception as e:
        print(f"  Warning: Failed to delete {video_dir}: {e}")
        return 0


def process_video(
    video_dir: Path,
    frame_interval: int = 10,
    dry_run: bool = False,
) -> dict:
    """
    Process a single video directory: upload to GCS and insert into DB.

    Returns a dict with:
        - status: "uploaded" | "duplicate" | "error"
        - video_id: the video ID (if found)
        - can_cleanup: whether it's safe to delete local files
        - record: the inserted DB record (if uploaded)
    """
    info = extract_video_info(video_dir)

    # Need at least a video_id to proceed
    if not info["video_id"]:
        print(f"  Skipping {video_dir.name}: No video_id found")
        return {"status": "error", "reason": "no_video_id", "can_cleanup": False}

    # Check if already in database
    if db.video_exists(info["video_id"]):
        print(f"  Already uploaded: {info['video_id']}")
        return {
            "status": "duplicate",
            "video_id": info["video_id"],
            "can_cleanup": True,  # Safe to delete - already in cloud
        }

    print(f"  Video ID: {info['video_id']}")
    print(f"  Author: @{info['author']}")
    print(f"  Frames: {info['frame_count']}")

    # Upload to GCS
    try:
        gcs_prefix, frames_uploaded = upload_to_gcs(
            video_dir, info["video_id"], frame_interval, dry_run
        )
    except Exception as e:
        print(f"  GCS upload failed: {e}")
        return {"status": "error", "video_id": info["video_id"], "reason": str(e), "can_cleanup": False}

    if dry_run:
        print(f"  [DRY RUN] Would insert into database")
        return {
            "status": "uploaded",
            "video_id": info["video_id"],
            "can_cleanup": True,
            "dry_run": True,
        }

    # Insert into database
    try:
        record = db.insert_video(
            video_id=info["video_id"],
            url=info["url"] or f"https://www.tiktok.com/@{info['author']}/video/{info['video_id']}",
            author=info["author"],
            title=info["title"],
            duration_sec=info["duration_sec"],
            transcript=info["transcript"],
            ocr_text=info["ocr_text"],
            gcs_prefix=gcs_prefix,
            frame_count=frames_uploaded,
            processed_at=datetime.now(),
        )
        print(f"  Inserted into database (id: {record.get('id')})")
        return {
            "status": "uploaded",
            "video_id": info["video_id"],
            "can_cleanup": True,
            "record": record,
        }
    except Exception as e:
        print(f"  Database insert failed: {e}")
        return {"status": "error", "video_id": info["video_id"], "reason": str(e), "can_cleanup": False}


def main():
    parser = argparse.ArgumentParser(
        description="Upload processed TikTok videos to GCS and Supabase"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=Path,
        default=Path(__file__).parent / "output",
        help="Output directory to scan (default: ./output)",
    )
    parser.add_argument(
        "--frame-interval", "-f",
        type=int,
        default=10,
        help="Upload every Nth frame (default: 10)",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be uploaded without actually uploading",
    )
    parser.add_argument(
        "--keep", "-k",
        action="store_true",
        help="Keep local files after upload (default: delete after successful upload)",
    )

    args = parser.parse_args()

    if not args.output_dir.exists():
        print(f"Error: Output directory not found: {args.output_dir}")
        sys.exit(1)

    print(f"=== TikTok Upload to GCS + Supabase ===")
    print(f"Output dir: {args.output_dir}")
    print(f"GCS bucket: gs://{GCS_BUCKET}")
    print(f"Frame interval: every {args.frame_interval}th frame")
    if args.dry_run:
        print("Mode: DRY RUN (no actual uploads)")
    if args.keep:
        print("Keep: ON (local files will be preserved)")
    print()

    # Find processed videos
    video_dirs = find_processed_videos(args.output_dir)
    print(f"Found {len(video_dirs)} processed video(s)")
    print()

    # Process each video
    uploaded = 0
    duplicates = 0
    errors = 0
    cleaned_up = 0
    space_freed_mb = 0

    for i, video_dir in enumerate(video_dirs, 1):
        print(f"[{i}/{len(video_dirs)}] {video_dir.name}")

        result = process_video(video_dir, args.frame_interval, args.dry_run)

        # Track stats
        if result["status"] == "uploaded":
            uploaded += 1
        elif result["status"] == "duplicate":
            duplicates += 1
        else:
            errors += 1

        # Cleanup by default (unless --keep)
        if not args.keep and result.get("can_cleanup"):
            freed = delete_video_dir(video_dir, args.dry_run)
            if freed > 0:
                cleaned_up += 1
                space_freed_mb += freed

        print()

    # Summary
    print("=" * 40)
    print(f"Uploaded: {uploaded}")
    print(f"Duplicates (already in DB): {duplicates}")
    print(f"Errors: {errors}")

    if not args.keep:
        print(f"Cleaned up: {cleaned_up} directories ({space_freed_mb:.1f} MB freed)")

    if not args.dry_run:
        stats = db.get_stats()
        print(f"Total videos in database: {stats['total_videos']}")


if __name__ == "__main__":
    main()
