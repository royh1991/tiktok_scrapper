#!/usr/bin/env python3
"""
Upload processed TikTok videos to Google Cloud Storage and Supabase.

This script uploads:
- Video file to GCS (optional, can skip to save storage)
- metadata.json content to database
- transcript.txt to database
- ocr.json items to database
- Key frames to GCS

Before uploading, validates that processing was successful:
- transcript.txt exists and has content
- ocr.json exists and is valid JSON
- audio.mp3 exists

Usage:
    python upload.py                      # Upload all processed videos
    python upload.py --dry-run            # Preview what would happen
    python upload.py --keep               # Upload but keep local files
    python upload.py --include-video      # Also upload video.mp4 to GCS
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from google.cloud import storage

import db

# Load environment variables
load_dotenv(Path(__file__).parent.parent / '.env')

GCS_BUCKET = os.getenv("GCS_BUCKET", "tiktokscrapper-videos")


def get_gcs_client() -> storage.Client:
    """Get Google Cloud Storage client."""
    return storage.Client()


def find_processed_videos(output_dir: Path) -> list[Path]:
    """
    Find all video directories that have been processed.

    A processed directory has video.mp4 and transcript.txt.
    """
    videos = []
    for item in output_dir.iterdir():
        if item.is_dir():
            has_video = (item / "video.mp4").exists()
            has_transcript = (item / "transcript.txt").exists()
            if has_video and has_transcript:
                videos.append(item)
    return sorted(videos)


def validate_processing(video_dir: Path) -> tuple[bool, list[str]]:
    """
    Validate that a video was processed successfully.

    Returns (is_valid, list_of_issues).
    """
    issues = []

    # Check video file
    if not (video_dir / "video.mp4").exists():
        issues.append("Missing video.mp4")

    # Check transcript
    transcript_path = video_dir / "transcript.txt"
    if not transcript_path.exists():
        issues.append("Missing transcript.txt")
    else:
        content = transcript_path.read_text().strip()
        if len(content) < 3:
            issues.append("Transcript is empty or too short")

    # Check OCR
    ocr_path = video_dir / "ocr.json"
    if not ocr_path.exists():
        issues.append("Missing ocr.json")
    else:
        try:
            with open(ocr_path) as f:
                ocr_data = json.load(f)
            if not isinstance(ocr_data, dict):
                issues.append("ocr.json is not a valid object")
        except json.JSONDecodeError as e:
            issues.append(f"ocr.json is invalid JSON: {e}")

    # Check audio
    if not (video_dir / "audio.mp3").exists():
        issues.append("Missing audio.mp3")

    # Check metadata
    if not (video_dir / "metadata.json").exists():
        issues.append("Missing metadata.json")

    return len(issues) == 0, issues


def extract_video_info(video_dir: Path) -> dict:
    """Extract all video information from the processed directory."""
    info = {
        "dir_name": video_dir.name,
        "video_id": None,
        "url": None,
        "author": None,
        "author_nickname": None,
        "caption": None,
        "transcript": None,
        "ocr_items": [],
        "ocr_scenes": 0,
        "frame_count": 0,
    }

    # Read metadata.json
    metadata_path = video_dir / "metadata.json"
    if metadata_path.exists():
        try:
            with open(metadata_path) as f:
                metadata = json.load(f)
                info["video_id"] = metadata.get("video_id")
                info["url"] = metadata.get("video_url")
                info["author"] = metadata.get("creator", "").lstrip("@")
                info["author_nickname"] = metadata.get("creator_nickname", "")
                info["caption"] = metadata.get("caption", "")
        except json.JSONDecodeError:
            pass

    # Fallback: extract from directory name if no metadata
    if not info["video_id"]:
        # Directory name is usually the video ID
        info["video_id"] = video_dir.name

    # Read transcript
    transcript_path = video_dir / "transcript.txt"
    if transcript_path.exists():
        info["transcript"] = transcript_path.read_text().strip()

    # Read OCR results
    ocr_path = video_dir / "ocr.json"
    if ocr_path.exists():
        try:
            with open(ocr_path) as f:
                ocr_data = json.load(f)
                info["ocr_items"] = ocr_data.get("items", [])
                info["ocr_scenes"] = ocr_data.get("scenes", 0)
        except json.JSONDecodeError:
            pass

    # Count frames
    frames_dir = video_dir / "frames"
    if frames_dir.exists():
        info["frame_count"] = len(list(frames_dir.glob("*.jpg")))

    return info


def select_key_frames(video_dir: Path, max_frames: int = 20) -> list[Path]:
    """
    Select key frames for upload.

    Uses scene detection - frames are already selected by process.py,
    so we just need to limit the count if too many.
    """
    frames_dir = video_dir / "frames"
    if not frames_dir.exists():
        return []

    frame_files = sorted(frames_dir.glob("*.jpg"))
    if not frame_files:
        return []

    # If under limit, return all
    if len(frame_files) <= max_frames:
        return frame_files

    # Otherwise, sample evenly
    step = (len(frame_files) - 1) / (max_frames - 1)
    indices = [int(i * step) for i in range(max_frames)]
    return [frame_files[i] for i in indices]


def upload_to_gcs(
    video_dir: Path,
    video_id: str,
    include_video: bool = False,
    max_frames: int = 20,
    dry_run: bool = False,
) -> tuple[str, int, int]:
    """
    Upload video artifacts to GCS.

    Returns (gcs_prefix, frames_uploaded, total_bytes).
    """
    client = get_gcs_client()
    bucket = client.bucket(GCS_BUCKET)
    gcs_prefix = f"videos/{video_id}/"

    files_to_upload = []
    total_bytes = 0

    # Optionally upload video file
    if include_video:
        video_path = video_dir / "video.mp4"
        if video_path.exists():
            files_to_upload.append((video_path, f"{gcs_prefix}video.mp4"))

    # Upload metadata and processing results
    for filename in ["metadata.json", "transcript.txt", "ocr.json", "transcript_timestamps.json", "audio.mp3"]:
        local_path = video_dir / filename
        if local_path.exists():
            files_to_upload.append((local_path, f"{gcs_prefix}{filename}"))

    # Select and upload key frames
    key_frames = select_key_frames(video_dir, max_frames)
    frames_uploaded = len(key_frames)

    for frame_path in key_frames:
        gcs_path = f"{gcs_prefix}frames/{frame_path.name}"
        files_to_upload.append((frame_path, gcs_path))

    # Upload files
    for local_path, gcs_path in files_to_upload:
        file_size = local_path.stat().st_size
        total_bytes += file_size

        if dry_run:
            print(f"    [DRY RUN] Would upload: {local_path.name} ({file_size/1024:.1f}KB)")
        else:
            blob = bucket.blob(gcs_path)
            blob.upload_from_filename(str(local_path))

    if not dry_run:
        print(f"    Uploaded {len(files_to_upload)} files ({total_bytes/1024/1024:.2f}MB)")

    return gcs_prefix, frames_uploaded, total_bytes


def insert_to_database(
    video_id: str,
    info: dict,
    gcs_prefix: str,
    frames_uploaded: int,
    dry_run: bool = False,
) -> Optional[dict]:
    """
    Insert video record into Supabase database.

    Returns the inserted record or None on error.
    """
    # Combine OCR items into a single text for search
    ocr_text = "\n".join(info.get("ocr_items", [])) if info.get("ocr_items") else None

    if dry_run:
        print(f"    [DRY RUN] Would insert: video_id={video_id}, author={info.get('author')}")
        return {"id": "dry_run", "video_id": video_id}

    try:
        record = db.insert_video(
            video_id=video_id,
            url=info.get("url") or f"https://www.tiktok.com/@{info.get('author', 'unknown')}/video/{video_id}",
            author=info.get("author"),
            title=info.get("caption"),
            transcript=info.get("transcript"),
            ocr_text=ocr_text,
            gcs_prefix=gcs_prefix,
            frame_count=frames_uploaded,
            processed_at=datetime.now(),
        )
        return record
    except Exception as e:
        print(f"    Database insert failed: {e}")
        return None


def delete_video_dir(video_dir: Path, dry_run: bool = False) -> float:
    """
    Delete a video directory and all its contents.

    Returns the size in MB that was freed.
    """
    try:
        size_mb = sum(f.stat().st_size for f in video_dir.rglob("*") if f.is_file()) / (1024 * 1024)
    except Exception:
        size_mb = 0

    if dry_run:
        print(f"    [DRY RUN] Would delete: {video_dir.name} ({size_mb:.1f}MB)")
        return size_mb

    try:
        shutil.rmtree(video_dir)
        return size_mb
    except Exception as e:
        print(f"    Warning: Failed to delete {video_dir}: {e}")
        return 0


def process_video(
    video_dir: Path,
    include_video: bool = False,
    max_frames: int = 20,
    dry_run: bool = False,
) -> dict:
    """
    Process a single video directory: validate, upload to GCS, insert into DB.

    Returns a result dict.
    """
    result = {
        "video_dir": str(video_dir),
        "status": "pending",
        "can_cleanup": False,
    }

    # Validate processing
    is_valid, issues = validate_processing(video_dir)
    if not is_valid:
        print(f"    Validation failed:")
        for issue in issues:
            print(f"      - {issue}")
        result["status"] = "validation_failed"
        result["issues"] = issues
        return result

    # Extract info
    info = extract_video_info(video_dir)
    video_id = info.get("video_id")

    if not video_id:
        print(f"    Error: Could not determine video_id")
        result["status"] = "error"
        result["reason"] = "no_video_id"
        return result

    result["video_id"] = video_id

    # Check if already in database
    if db.video_exists(video_id):
        print(f"    Already in database: {video_id}")
        result["status"] = "duplicate"
        result["can_cleanup"] = True
        return result

    print(f"    Video ID: {video_id}")
    print(f"    Author: @{info.get('author', 'unknown')}")
    print(f"    Caption: {(info.get('caption') or '')[:50]}...")
    print(f"    Transcript: {len(info.get('transcript', ''))} chars")
    print(f"    OCR items: {len(info.get('ocr_items', []))}")

    # Upload to GCS
    try:
        gcs_prefix, frames_uploaded, total_bytes = upload_to_gcs(
            video_dir, video_id, include_video, max_frames, dry_run
        )
    except Exception as e:
        print(f"    GCS upload failed: {e}")
        result["status"] = "gcs_failed"
        result["reason"] = str(e)
        return result

    # Insert into database
    record = insert_to_database(video_id, info, gcs_prefix, frames_uploaded, dry_run)

    if record:
        result["status"] = "success"
        result["can_cleanup"] = True
        result["gcs_prefix"] = gcs_prefix
        result["frames_uploaded"] = frames_uploaded
        result["record_id"] = record.get("id")
    else:
        result["status"] = "db_failed"

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Upload processed TikTok videos to GCS and Supabase"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=Path,
        default=Path(__file__).parent.parent / "output",
        help="Output directory to scan",
    )
    parser.add_argument(
        "--max-frames", "-f",
        type=int,
        default=20,
        help="Max frames to upload per video (default: 20)",
    )
    parser.add_argument(
        "--include-video",
        action="store_true",
        help="Also upload video.mp4 files to GCS",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Preview without uploading",
    )
    parser.add_argument(
        "--keep", "-k",
        action="store_true",
        help="Keep local files after upload",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("TikTok Upload to GCS + Supabase")
    print("=" * 60)
    print(f"Output dir: {args.output_dir}")
    print(f"GCS bucket: gs://{GCS_BUCKET}")
    print(f"Max frames: {args.max_frames}")
    if args.include_video:
        print("Include video: YES")
    if args.dry_run:
        print("Mode: DRY RUN")
    if args.keep:
        print("Keep files: YES")
    print("=" * 60)
    print()

    if not args.output_dir.exists():
        print(f"Error: Output directory not found: {args.output_dir}")
        sys.exit(1)

    # Find processed videos
    video_dirs = find_processed_videos(args.output_dir)
    print(f"Found {len(video_dirs)} processed video(s)")
    print()

    if not video_dirs:
        return

    # Process each video
    uploaded = 0
    duplicates = 0
    failed = 0
    cleaned_up = 0
    space_freed_mb = 0

    for i, video_dir in enumerate(video_dirs, 1):
        print(f"[{i}/{len(video_dirs)}] {video_dir.name}")

        result = process_video(
            video_dir,
            include_video=args.include_video,
            max_frames=args.max_frames,
            dry_run=args.dry_run,
        )

        if result["status"] == "success":
            uploaded += 1
        elif result["status"] == "duplicate":
            duplicates += 1
        else:
            failed += 1

        # Cleanup unless --keep
        if not args.keep and result.get("can_cleanup"):
            freed = delete_video_dir(video_dir, args.dry_run)
            if freed > 0:
                cleaned_up += 1
                space_freed_mb += freed
                print(f"    Cleaned up ({freed:.1f}MB)")

        print()

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Uploaded: {uploaded}")
    print(f"Duplicates: {duplicates}")
    print(f"Failed: {failed}")

    if not args.keep:
        print(f"Cleaned up: {cleaned_up} directories ({space_freed_mb:.1f}MB freed)")

    if not args.dry_run:
        try:
            stats = db.get_stats()
            print(f"Total videos in database: {stats['total_videos']}")
        except Exception as e:
            print(f"Could not get stats: {e}")


if __name__ == "__main__":
    main()
