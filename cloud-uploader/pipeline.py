#!/usr/bin/env python3
"""
TikTok Research Pipeline

Orchestrates the full pipeline for each query in research_list.csv:
1. Search for TikTok videos using Serper API
2. Download videos using zendriver
3. Process videos (OCR + transcription)
4. Validate processing was successful
5. Upload to GCS and database

Features:
- Retry logic with exponential backoff for all steps
- Failure tracking and logging
- Resume capability from progress.json
- Per-video retry for processing failures
- Comprehensive file logging for debugging

Usage:
    python pipeline.py                    # Process all unprocessed queries
    python pipeline.py --start 0 --count 10  # Process queries 0-9
    python pipeline.py --query "tokyo ramen"  # Process specific query
    python pipeline.py --dry-run          # Preview without executing
"""

import argparse
import asyncio
import csv
import json
import logging
import os
import random
import shutil
import signal
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

# Graceful shutdown flag
shutdown_requested = False

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    shutdown_requested = True
    if logger:
        logger.warning("Shutdown requested, finishing current query...")
    print("\n⚠️  Shutdown requested. Finishing current query and saving progress...")

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

import db

# Load environment variables
load_dotenv(Path(__file__).parent.parent / '.env')

# Configuration
BASE_DIR = Path(__file__).parent.parent
RESEARCH_LIST = BASE_DIR / "research_list.csv"
OUTPUT_DIR = BASE_DIR / "output"
PROGRESS_FILE = BASE_DIR / "cloud-uploader" / "progress.json"
FAILURES_FILE = BASE_DIR / "cloud-uploader" / "failures.json"
LOG_DIR = BASE_DIR / "cloud-uploader" / "logs"

# Retry configuration
MAX_SEARCH_RETRIES = 3
MAX_DOWNLOAD_RETRIES = 2
MAX_PROCESS_RETRIES = 3
MAX_UPLOAD_RETRIES = 3
RETRY_DELAY_BASE = 2  # seconds, doubles each retry

# Random wait times to avoid rate limiting (in seconds)
MIN_WAIT_BEFORE_DOWNLOAD = 2
MAX_WAIT_BEFORE_DOWNLOAD = 5
MIN_WAIT_BETWEEN_QUERIES = 5
MAX_WAIT_BETWEEN_QUERIES = 10

# Import search function
from tiktok_search import google_search


def setup_logging() -> logging.Logger:
    """Set up logging to both file and console."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Create logger
    logger = logging.getLogger("pipeline")
    logger.setLevel(logging.DEBUG)

    # Clear existing handlers
    logger.handlers = []

    # File handler - detailed logging
    log_file = LOG_DIR / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    # Console handler - less verbose
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # Also create a latest.log symlink
    latest_log = LOG_DIR / "latest.log"
    if latest_log.exists() or latest_log.is_symlink():
        latest_log.unlink()
    latest_log.symlink_to(log_file.name)

    logger.info(f"Logging to: {log_file}")

    return logger


# Global logger
logger = None


def log_failure(failure_type: str, query_info: dict, error: str, details: dict = None):
    """Log a failure to the failures file."""
    failures = []
    if FAILURES_FILE.exists():
        try:
            with open(FAILURES_FILE) as f:
                failures = json.load(f)
        except:
            failures = []

    failure = {
        "timestamp": datetime.now().isoformat(),
        "type": failure_type,
        "query_index": query_info.get("index"),
        "query": query_info.get("query"),
        "city": query_info.get("city"),
        "country": query_info.get("country"),
        "error": error,
        "details": details or {},
    }
    failures.append(failure)

    FAILURES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(FAILURES_FILE, 'w') as f:
        json.dump(failures, f, indent=2)

    if logger:
        logger.error(f"FAILURE [{failure_type}] {query_info.get('query', '')[:50]}: {error}")


def load_progress() -> dict:
    """Load progress from file."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"processed_queries": [], "stats": {"total": 0, "success": 0, "failed": 0}}


def save_progress(progress: dict):
    """Save progress to file."""
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)


def mark_query_completed(csv_path: Path, query_index: int, status: str):
    """
    Mark a query as completed in the CSV by updating the completed_at column.

    Creates the column if it doesn't exist.
    """
    # Read all rows
    rows = []
    fieldnames = []

    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    # Add completed_at column if it doesn't exist
    if 'completed_at' not in fieldnames:
        fieldnames.append('completed_at')
    if 'status' not in fieldnames:
        fieldnames.append('status')

    # Update the specific row (query_index is 0-based, matching row index)
    if 0 <= query_index < len(rows):
        rows[query_index]['completed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        rows[query_index]['status'] = status

    # Write back
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    if logger:
        logger.debug(f"Marked query {query_index} as {status} in CSV")


def random_wait(min_seconds: float, max_seconds: float, reason: str = ""):
    """Wait a random amount of time to avoid rate limiting."""
    wait_time = random.uniform(min_seconds, max_seconds)
    if logger:
        logger.info(f"Waiting {wait_time:.1f}s {reason}")
    print(f"        Waiting {wait_time:.1f}s {reason}...")
    time.sleep(wait_time)


def get_disk_space_gb(path: Path = Path("/")) -> float:
    """Get available disk space in GB."""
    try:
        stat = shutil.disk_usage(path)
        return stat.free / (1024 ** 3)
    except Exception:
        return float('inf')  # Assume enough space if check fails


def check_disk_space(min_gb: float = 2.0) -> bool:
    """Check if there's enough disk space to continue."""
    available = get_disk_space_gb(OUTPUT_DIR if OUTPUT_DIR.exists() else Path("/"))
    if available < min_gb:
        if logger:
            logger.error(f"Low disk space: {available:.1f}GB available (need {min_gb}GB)")
        print(f"⚠️  Low disk space: {available:.1f}GB available")
        return False
    return True


def cleanup_chrome_processes():
    """Kill any stale Chrome processes to free resources."""
    try:
        # Kill zombie chrome processes
        subprocess.run(["pkill", "-9", "-f", "chrome.*--type=renderer"],
                      capture_output=True, timeout=5)
        # Small delay to let processes clean up
        time.sleep(0.5)
        if logger:
            logger.debug("Cleaned up Chrome processes")
    except Exception as e:
        if logger:
            logger.debug(f"Chrome cleanup: {e}")


def cleanup_browser_profiles():
    """Clean browser profiles to prevent bloat and detection."""
    profiles_dir = BASE_DIR / "browser_profiles"
    if profiles_dir.exists():
        try:
            # Remove crash dumps and cache
            for pattern in ["**/Crash*", "**/Cache*", "**/Code Cache*", "**/GPUCache*"]:
                for f in profiles_dir.glob(pattern):
                    if f.is_dir():
                        shutil.rmtree(f, ignore_errors=True)
                    elif f.is_file():
                        f.unlink(missing_ok=True)
            if logger:
                logger.debug("Cleaned browser profiles")
        except Exception as e:
            if logger:
                logger.debug(f"Profile cleanup: {e}")


def load_queries(csv_path: Path, start: int = 0, count: Optional[int] = None) -> list[dict]:
    """Load queries from research_list.csv."""
    queries = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i < start:
                continue
            if count and len(queries) >= count:
                break
            queries.append({
                "index": i,
                "region": row.get("region", ""),
                "city": row.get("city", ""),
                "country": row.get("country", ""),
                "query": row.get("search_query", ""),
            })
    return queries


def run_search_with_retry(query: str, max_results: int = 20, query_info: dict = None) -> list[str]:
    """Run TikTok search with retry logic."""
    print(f"  [1/4] Searching: '{query}'...")
    logger.info(f"SEARCH: '{query}' (max_results={max_results})")

    last_error = None
    for attempt in range(MAX_SEARCH_RETRIES):
        try:
            logger.debug(f"Search attempt {attempt + 1}/{MAX_SEARCH_RETRIES}")
            result = asyncio.run(google_search(query, num_results=max_results))
            urls = result.get('urls', [])
            print(f"        Found {len(urls)} videos")
            logger.info(f"Search found {len(urls)} URLs")
            for i, url in enumerate(urls):
                logger.debug(f"  URL {i+1}: {url}")
            return urls
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Search attempt {attempt + 1} failed: {e}")
            if attempt < MAX_SEARCH_RETRIES - 1:
                delay = RETRY_DELAY_BASE * (2 ** attempt)
                print(f"        Search failed (attempt {attempt + 1}/{MAX_SEARCH_RETRIES}): {e}")
                print(f"        Retrying in {delay}s...")
                time.sleep(delay)
            else:
                print(f"        Search failed after {MAX_SEARCH_RETRIES} attempts: {e}")
                logger.error(f"Search failed after {MAX_SEARCH_RETRIES} attempts: {e}")

    if query_info:
        log_failure("search", query_info, last_error)
    return []


def run_download_with_retry(urls: list[str], output_dir: Path, workers: int = 3, query_info: dict = None, local: bool = False) -> tuple[int, list[str]]:
    """
    Run TikTok downloader with retry logic.

    Returns (downloaded_count, failed_urls).
    """
    if not urls:
        return 0, []

    print(f"  [2/4] Downloading {len(urls)} videos...")
    logger.info(f"DOWNLOAD: {len(urls)} URLs to {output_dir}")

    # Random wait before downloading to avoid rate limiting
    random_wait(MIN_WAIT_BEFORE_DOWNLOAD, MAX_WAIT_BEFORE_DOWNLOAD, "before download")

    output_dir.mkdir(parents=True, exist_ok=True)

    all_failed_urls = []
    total_downloaded = 0
    urls_to_try = urls.copy()

    for attempt in range(MAX_DOWNLOAD_RETRIES):
        if not urls_to_try:
            break

        logger.debug(f"Download attempt {attempt + 1}/{MAX_DOWNLOAD_RETRIES}, {len(urls_to_try)} URLs")

        # Write URLs to temp file
        temp_urls = output_dir / "temp_urls.txt"
        with open(temp_urls, 'w') as f:
            f.write('\n'.join(urls_to_try))

        try:
            cmd = [
                sys.executable, str(BASE_DIR / "tiktok_downloader.py"),
                "--workers", str(workers),
                "-o", str(output_dir),
            ]
            if local:
                cmd.append("--dev")
            cmd.extend(["download", "--file", str(temp_urls)])
            logger.debug(f"Running: {' '.join(cmd)}")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if result.returncode != 0:
                logger.warning(f"Downloader returned code {result.returncode}")
                logger.debug(f"STDOUT: {result.stdout[-500:] if result.stdout else 'empty'}")
                logger.debug(f"STDERR: {result.stderr[-500:] if result.stderr else 'empty'}")

            # Count downloaded videos
            downloaded_dirs = [d for d in output_dir.iterdir() if d.is_dir() and (d / "video.mp4").exists()]
            downloaded_ids = {d.name for d in downloaded_dirs}

            current_downloaded = len(downloaded_dirs)

            if attempt == 0:
                total_downloaded = current_downloaded
                print(f"        Downloaded {current_downloaded}/{len(urls)} videos")
                logger.info(f"Downloaded {current_downloaded}/{len(urls)} videos")
            else:
                new_downloads = current_downloaded - total_downloaded
                total_downloaded = current_downloaded
                print(f"        Retry {attempt}: Downloaded {new_downloads} more videos (total: {total_downloaded})")
                logger.info(f"Retry {attempt}: +{new_downloads} videos (total: {total_downloaded})")

            # Find which URLs failed (extract video ID from URL)
            failed_urls = []
            for url in urls_to_try:
                # Extract video ID from URL
                import re
                match = re.search(r'/video/(\d+)', url)
                if match:
                    video_id = match.group(1)
                    if video_id not in downloaded_ids:
                        failed_urls.append(url)
                        logger.debug(f"Failed to download: {url}")

            urls_to_try = failed_urls

            if not failed_urls:
                logger.info("All URLs downloaded successfully")
                break

            if attempt < MAX_DOWNLOAD_RETRIES - 1 and failed_urls:
                delay = RETRY_DELAY_BASE * (2 ** attempt)
                print(f"        {len(failed_urls)} failed, retrying in {delay}s...")
                logger.info(f"{len(failed_urls)} failed, retrying in {delay}s")
                time.sleep(delay)

        except subprocess.TimeoutExpired:
            logger.error(f"Download timed out (attempt {attempt + 1})")
            print(f"        Download timed out (attempt {attempt + 1})")
            if attempt < MAX_DOWNLOAD_RETRIES - 1:
                time.sleep(RETRY_DELAY_BASE)
        except Exception as e:
            logger.error(f"Download error (attempt {attempt + 1}): {e}")
            print(f"        Download error (attempt {attempt + 1}): {e}")
            if attempt < MAX_DOWNLOAD_RETRIES - 1:
                time.sleep(RETRY_DELAY_BASE)
        finally:
            if temp_urls.exists():
                temp_urls.unlink()

    # Log failed URLs
    if urls_to_try and query_info:
        log_failure("download", query_info, f"{len(urls_to_try)} URLs failed to download",
                   {"failed_urls": urls_to_try[:10]})  # Log first 10

    return total_downloaded, urls_to_try


def run_process_single_video(video_dir: Path, whisper_model: str = "base", batch_ocr: bool = False, use_claude_code: bool = False) -> bool:
    """Process a single video with retry logic."""
    logger.debug(f"Processing single video: {video_dir.name}")

    for attempt in range(MAX_PROCESS_RETRIES):
        try:
            cmd = [
                sys.executable, str(BASE_DIR / "process.py"),
                str(video_dir),
                "--model", whisper_model,
            ]

            if use_claude_code:
                cmd.append("--use-claude-code")
            elif batch_ocr:
                cmd.append("--batch-ocr")

            if attempt > 0:
                cmd.append("--reprocess")
                logger.debug(f"Reprocessing attempt {attempt + 1}")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            # Check if processing succeeded
            has_transcript = (video_dir / "transcript.txt").exists()
            has_ocr = (video_dir / "ocr.json").exists()
            has_audio = (video_dir / "audio.mp3").exists()

            if has_transcript and has_ocr and has_audio:
                # Transcript file exists (content can be empty for music-only videos)
                logger.debug(f"Successfully processed {video_dir.name}")
                return True

            logger.debug(f"Processing incomplete: transcript={has_transcript}, ocr={has_ocr}, audio={has_audio}")

            if attempt < MAX_PROCESS_RETRIES - 1:
                delay = RETRY_DELAY_BASE * (2 ** attempt)
                time.sleep(delay)

        except subprocess.TimeoutExpired:
            logger.warning(f"Processing timeout for {video_dir.name} (attempt {attempt + 1})")
            if attempt < MAX_PROCESS_RETRIES - 1:
                time.sleep(RETRY_DELAY_BASE)
        except Exception as e:
            logger.warning(f"Processing error for {video_dir.name}: {e}")
            if attempt < MAX_PROCESS_RETRIES - 1:
                time.sleep(RETRY_DELAY_BASE)

    logger.error(f"Failed to process {video_dir.name} after {MAX_PROCESS_RETRIES} attempts")
    return False


def run_process_with_retry(output_dir: Path, whisper_model: str = "base", query_info: dict = None, batch_ocr: bool = False, use_claude_code: bool = False) -> tuple[int, int]:
    """
    Run video processing with per-video retry logic.

    Returns (processed_count, failed_count).
    """
    video_dirs = [d for d in output_dir.iterdir() if d.is_dir() and (d / "video.mp4").exists()]

    if not video_dirs:
        return 0, 0

    logger.info(f"PROCESS: {len(video_dirs)} videos in {output_dir} (batch_ocr={batch_ocr}, use_claude_code={use_claude_code})")

    # Find unprocessed videos
    unprocessed = []
    already_processed = 0

    for d in video_dirs:
        has_transcript = (d / "transcript.txt").exists()
        has_ocr = (d / "ocr.json").exists()
        has_audio = (d / "audio.mp3").exists()

        if has_transcript and has_ocr and has_audio:
            # Transcript file exists (content can be empty for music-only videos)
            already_processed += 1
            logger.debug(f"Already processed: {d.name}")
            continue

        unprocessed.append(d)

    if not unprocessed:
        print(f"  [3/4] All {len(video_dirs)} videos already processed")
        logger.info(f"All {len(video_dirs)} videos already processed")
        return len(video_dirs), 0

    print(f"  [3/4] Processing {len(unprocessed)} videos...")
    logger.info(f"Processing {len(unprocessed)} unprocessed videos")

    # First, try batch processing
    try:
        cmd = [
            sys.executable, str(BASE_DIR / "process.py"),
            "--output", str(output_dir),
            "--model", whisper_model,
        ]
        if use_claude_code:
            cmd.append("--use-claude-code")
        elif batch_ocr:
            cmd.append("--batch-ocr")
        logger.debug(f"Batch processing: {' '.join(cmd)}")
        subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except Exception as e:
        logger.warning(f"Batch processing failed: {e}")

    # Now check which ones failed and retry individually
    processed = already_processed
    failed = 0
    failed_dirs = []

    for video_dir in unprocessed:
        has_transcript = (video_dir / "transcript.txt").exists()
        has_ocr = (video_dir / "ocr.json").exists()
        has_audio = (video_dir / "audio.mp3").exists()

        if has_transcript and has_ocr and has_audio:
            # Transcript file exists (content can be empty for music-only videos)
            processed += 1
            logger.debug(f"Batch processed: {video_dir.name}")
            continue

        # Try individual processing with retries
        print(f"        Retrying {video_dir.name}...")
        if run_process_single_video(video_dir, whisper_model, batch_ocr, use_claude_code):
            processed += 1
        else:
            failed += 1
            failed_dirs.append(video_dir.name)

    print(f"        Processed: {processed}, Failed: {failed}")
    logger.info(f"Processing complete: {processed} processed, {failed} failed")

    if failed_dirs and query_info:
        log_failure("process", query_info, f"{failed} videos failed processing",
                   {"failed_videos": failed_dirs[:10]})

    return processed, failed


def validate_processing(output_dir: Path) -> tuple[list[Path], list[Path]]:
    """
    Validate that all videos were processed successfully.

    Returns (valid_dirs, invalid_dirs).
    """
    valid = []
    invalid = []

    for video_dir in output_dir.iterdir():
        if not video_dir.is_dir():
            continue
        if not (video_dir / "video.mp4").exists():
            continue

        is_valid = True
        issues = []

        # Check transcript
        transcript_path = video_dir / "transcript.txt"
        if not transcript_path.exists():
            is_valid = False
            issues.append("no transcript")
        else:
            try:
                content = transcript_path.read_text().strip()
                if not content or len(content) < 3:
                    is_valid = False
                    issues.append("empty transcript")
            except:
                is_valid = False
                issues.append("transcript read error")

        # Check OCR
        ocr_path = video_dir / "ocr.json"
        if not ocr_path.exists():
            is_valid = False
            issues.append("no ocr.json")
        else:
            try:
                with open(ocr_path) as f:
                    ocr_data = json.load(f)
            except json.JSONDecodeError:
                is_valid = False
                issues.append("invalid ocr.json")

        # Check audio
        audio_path = video_dir / "audio.mp3"
        if not audio_path.exists():
            is_valid = False
            issues.append("no audio.mp3")

        if is_valid:
            valid.append(video_dir)
        else:
            invalid.append(video_dir)
            logger.debug(f"Invalid video {video_dir.name}: {', '.join(issues)}")

    return valid, invalid


def delete_video_file(video_dir: Path, dry_run: bool = False) -> float:
    """
    Delete only the video.mp4 file to save space.

    Returns size in MB freed.
    """
    video_path = video_dir / "video.mp4"
    if not video_path.exists():
        return 0

    try:
        size_mb = video_path.stat().st_size / (1024 * 1024)
        if not dry_run:
            video_path.unlink()
            logger.debug(f"Deleted video.mp4: {video_dir.name} ({size_mb:.1f}MB)")
        return size_mb
    except Exception as e:
        logger.warning(f"Failed to delete video.mp4 in {video_dir.name}: {e}")
        return 0


def run_upload_with_retry(output_dir: Path, dry_run: bool = False, query_info: dict = None) -> tuple[int, int, float]:
    """
    Upload processed videos with retry logic.

    Returns (uploaded_count, failed_count, space_freed_mb).
    """
    valid_dirs, _ = validate_processing(output_dir)

    if not valid_dirs:
        return 0, 0, 0

    print(f"  [4/4] Uploading {len(valid_dirs)} videos...")
    logger.info(f"UPLOAD: {len(valid_dirs)} valid videos")

    last_error = None
    for attempt in range(MAX_UPLOAD_RETRIES):
        try:
            cmd = [
                sys.executable, str(BASE_DIR / "cloud-uploader" / "upload.py"),
                "--output-dir", str(output_dir),
                "--keep",  # Keep files, let pipeline handle mp4 deletion
            ]

            # Pass query string if available
            if query_info and query_info.get("query"):
                cmd.extend(["--query", query_info["query"]])

            if dry_run:
                cmd.append("--dry-run")

            logger.debug(f"Upload attempt {attempt + 1}: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            # Parse output for counts
            uploaded = 0
            failed = 0

            for line in result.stdout.splitlines():
                if "Uploaded:" in line:
                    try:
                        uploaded = int(line.split(":")[1].strip().split()[0])
                    except:
                        pass
                if "Failed:" in line:
                    try:
                        failed = int(line.split(":")[1].strip().split()[0])
                    except:
                        pass

            if uploaded > 0 or result.returncode == 0:
                print(f"        Uploaded {uploaded} videos")
                logger.info(f"Uploaded {uploaded} videos, {failed} failed")
                if failed > 0:
                    print(f"        Failed: {failed}")

                # Delete video.mp4 files ONLY for successfully uploaded videos
                # Check if video is now in DB before deleting
                space_freed = 0
                for video_dir in valid_dirs:
                    video_id = video_dir.name
                    # Only delete if video was successfully uploaded to database
                    if db.video_exists(video_id):
                        space_freed += delete_video_file(video_dir, dry_run)
                    else:
                        logger.debug(f"Keeping video.mp4 for {video_id} (not in DB yet)")

                if space_freed > 0:
                    logger.info(f"Freed {space_freed:.1f}MB by deleting video files")

                return uploaded, failed, space_freed

            # If no uploads, might be an error
            if attempt < MAX_UPLOAD_RETRIES - 1:
                delay = RETRY_DELAY_BASE * (2 ** attempt)
                print(f"        Upload may have failed, retrying in {delay}s...")
                logger.warning(f"Upload may have failed, retrying in {delay}s")
                time.sleep(delay)

            last_error = result.stderr[:200] if result.stderr else "Unknown error"
            logger.debug(f"Upload stderr: {result.stderr[:500] if result.stderr else 'empty'}")

        except subprocess.TimeoutExpired:
            last_error = "Upload timed out"
            logger.error(f"Upload timed out (attempt {attempt + 1})")
            if attempt < MAX_UPLOAD_RETRIES - 1:
                delay = RETRY_DELAY_BASE * (2 ** attempt)
                print(f"        Upload timed out, retrying in {delay}s...")
                time.sleep(delay)
        except Exception as e:
            last_error = str(e)
            logger.error(f"Upload error (attempt {attempt + 1}): {e}")
            if attempt < MAX_UPLOAD_RETRIES - 1:
                delay = RETRY_DELAY_BASE * (2 ** attempt)
                print(f"        Upload error: {e}, retrying in {delay}s...")
                time.sleep(delay)

    print(f"        Upload failed after {MAX_UPLOAD_RETRIES} attempts")
    logger.error(f"Upload failed after {MAX_UPLOAD_RETRIES} attempts: {last_error}")
    if query_info:
        log_failure("upload", query_info, last_error)

    return 0, len(valid_dirs), 0


def process_query(
    query_info: dict,
    max_results: int = 20,
    workers: int = 3,
    whisper_model: str = "base",
    dry_run: bool = False,
    local: bool = False,
    batch_ocr: bool = False,
    use_claude_code: bool = False,
) -> dict:
    """
    Process a single query through the full pipeline with retry logic.

    Returns a result dict with status and stats.
    """
    query = query_info['query']
    index = query_info['index']

    logger.info("=" * 60)
    logger.info(f"QUERY {index}: {query}")
    logger.info(f"City: {query_info.get('city')}, Country: {query_info.get('country')}")

    # Create output directory for this query
    query_slug = query.replace(" ", "_")[:50]
    output_dir = OUTPUT_DIR / f"query_{index:05d}_{query_slug}"

    result = {
        "index": index,
        "query": query,
        "city": query_info.get("city", ""),
        "country": query_info.get("country", ""),
        "status": "pending",
        "videos_found": 0,
        "videos_downloaded": 0,
        "videos_processed": 0,
        "videos_uploaded": 0,
        "videos_failed": 0,
        "space_freed_mb": 0,
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
        "errors": [],
    }

    try:
        # Step 1: Search with retry
        urls = run_search_with_retry(query, max_results, query_info)
        result["videos_found"] = len(urls)

        if not urls:
            result["status"] = "search_failed"
            result["errors"].append("No results from search after retries")
            logger.warning(f"Query {index} failed: no search results")
            return result

        # Filter out videos already in database
        existing_ids = db.get_all_video_ids()
        urls_to_download = []
        skipped_count = 0

        import re
        for url in urls:
            match = re.search(r'/video/(\d+)', url)
            if match:
                video_id = match.group(1)
                if video_id in existing_ids:
                    logger.debug(f"Skipping already uploaded: {video_id}")
                    skipped_count += 1
                else:
                    urls_to_download.append(url)
            else:
                urls_to_download.append(url)

        if skipped_count > 0:
            print(f"        Skipping {skipped_count} already uploaded videos")
            logger.info(f"Skipped {skipped_count} videos already in database")

        if not urls_to_download:
            print(f"  All {len(urls)} videos already uploaded")
            result["status"] = "success"
            result["videos_uploaded"] = skipped_count  # Count as "already done"
            logger.info(f"Query {index}: all videos already uploaded")
            return result

        urls = urls_to_download

        if dry_run:
            print(f"  [DRY RUN] Would download {len(urls)} videos")
            result["status"] = "dry_run"
            return result

        # Step 2: Download with retry
        downloaded, failed_urls = run_download_with_retry(urls, output_dir, workers, query_info, local=local)
        result["videos_downloaded"] = downloaded

        if downloaded == 0:
            result["status"] = "download_failed"
            result["errors"].append("No videos downloaded after retries")
            logger.warning(f"Query {index} failed: no downloads")
            return result

        # Step 3: Process with per-video retry
        processed, process_failed = run_process_with_retry(output_dir, whisper_model, query_info, batch_ocr, use_claude_code)
        result["videos_processed"] = processed
        result["videos_failed"] += process_failed

        # Final validation
        valid, invalid = validate_processing(output_dir)
        result["videos_processed"] = len(valid)

        if len(valid) == 0:
            result["status"] = "processing_failed"
            result["errors"].append("No videos passed validation after retries")
            logger.warning(f"Query {index} failed: no valid videos after processing")
            return result

        # Step 4: Upload with retry
        uploaded, upload_failed, space_freed = run_upload_with_retry(output_dir, dry_run, query_info)
        result["videos_uploaded"] = uploaded
        result["videos_failed"] += upload_failed
        result["space_freed_mb"] = round(space_freed, 1)

        if uploaded == 0 and len(valid) > 0:
            result["status"] = "upload_failed"
            result["errors"].append("Upload failed after retries")
            logger.warning(f"Query {index} failed: upload failed")
            return result

        # Determine final status
        if uploaded > 0:
            if result["videos_failed"] > 0:
                result["status"] = "partial_success"
            else:
                result["status"] = "success"
        else:
            result["status"] = "failed"

        result["completed_at"] = datetime.now().isoformat()
        logger.info(f"Query {index} completed: {result['status']} (uploaded {uploaded}, failed {result['videos_failed']})")
        return result

    except Exception as e:
        result["status"] = "error"
        result["errors"].append(str(e))
        logger.exception(f"Query {index} error: {e}")
        log_failure("pipeline", query_info, str(e), {"traceback": traceback.format_exc()})
        return result


def main():
    global logger

    parser = argparse.ArgumentParser(description="TikTok Research Pipeline")
    parser.add_argument("--start", type=int, default=0, help="Starting query index")
    parser.add_argument("--count", type=int, help="Number of queries to process")
    parser.add_argument("--query", help="Process a specific query instead of CSV")
    parser.add_argument("--max-results", type=int, default=20, help="Max videos per query")
    parser.add_argument("--workers", type=int, default=3, help="Browser workers for download")
    parser.add_argument("--whisper-model", default="base", help="Whisper model for transcription")
    parser.add_argument("--dry-run", action="store_true", help="Search only, don't download")
    parser.add_argument("--resume", action="store_true", help="Skip already processed queries")
    parser.add_argument("--local", action="store_true", help="Use dev settings for local Mac development")
    parser.add_argument("--batch-ocr", action="store_true", help="Use Batch API for OCR (50% cheaper)")
    parser.add_argument("--use-claude-code", action="store_true", help="Use Claude Code CLI for OCR (uses subscription)")

    args = parser.parse_args()

    # Set up logging
    logger = setup_logging()

    print("=" * 60)
    print("TikTok Research Pipeline")
    print("=" * 60)

    logger.info("=" * 60)
    logger.info("TikTok Research Pipeline Started")
    logger.info(f"Args: {vars(args)}")

    # Load progress
    progress = load_progress()
    processed_set = set(progress.get("processed_queries", []))

    # Get queries
    if args.query:
        queries = [{
            "index": 0,
            "region": "Custom",
            "city": "Custom",
            "country": "Custom",
            "query": args.query,
        }]
    else:
        if not RESEARCH_LIST.exists():
            print(f"Error: Research list not found: {RESEARCH_LIST}")
            logger.error(f"Research list not found: {RESEARCH_LIST}")
            sys.exit(1)

        queries = load_queries(RESEARCH_LIST, args.start, args.count)

    print(f"Queries to process: {len(queries)}")
    print(f"Max results per query: {args.max_results}")
    print(f"Workers: {args.workers}")
    print(f"Whisper model: {args.whisper_model}")
    print(f"Retry config: search={MAX_SEARCH_RETRIES}, download={MAX_DOWNLOAD_RETRIES}, process={MAX_PROCESS_RETRIES}, upload={MAX_UPLOAD_RETRIES}")
    if args.dry_run:
        print("Mode: DRY RUN")
    if args.local:
        print("Mode: LOCAL (using --dev for downloader)")
    if args.use_claude_code:
        print("OCR: Claude Code CLI (uses subscription)")
    elif args.batch_ocr:
        print("OCR: Batch API (50% cheaper)")
    if args.resume:
        print(f"Resume: Skipping {len(processed_set)} already processed")
    print("=" * 60)
    print()

    logger.info(f"Queries: {len(queries)}, max_results: {args.max_results}, workers: {args.workers}")

    # Process each query
    results = []
    total_space_freed = 0

    for i, query_info in enumerate(queries, 1):
        # Check for shutdown request
        if shutdown_requested:
            print("\n🛑 Shutdown requested. Saving progress and exiting...")
            logger.info("Shutdown requested, exiting gracefully")
            break

        # Check disk space before each query
        if not check_disk_space(min_gb=1.0):
            print("❌ Insufficient disk space. Stopping to prevent issues.")
            logger.error("Stopping due to low disk space")
            break

        query_key = f"{query_info['index']}:{query_info['query']}"

        if args.resume and query_key in processed_set:
            print(f"[{i}/{len(queries)}] Skipping (already processed): {query_info['query'][:50]}")
            logger.info(f"Skipping already processed: {query_info['query'][:50]}")
            continue

        # Cleanup Chrome processes periodically (every 3 queries)
        if i > 1 and (i - 1) % 3 == 0:
            cleanup_chrome_processes()
            cleanup_browser_profiles()

        print(f"[{i}/{len(queries)}] {query_info['city']}, {query_info['country']}")
        print(f"    Query: {query_info['query'][:60]}...")

        result = process_query(
            query_info,
            max_results=args.max_results,
            workers=args.workers,
            whisper_model=args.whisper_model,
            dry_run=args.dry_run,
            local=args.local,
            batch_ocr=args.batch_ocr,
            use_claude_code=args.use_claude_code,
        )

        results.append(result)
        total_space_freed += result.get("space_freed_mb", 0)

        # Update progress
        if result["status"] in ["success", "partial_success"]:
            progress["processed_queries"].append(query_key)
            progress["stats"]["success"] = progress["stats"].get("success", 0) + 1
        else:
            progress["stats"]["failed"] = progress["stats"].get("failed", 0) + 1

        progress["stats"]["total"] = progress["stats"].get("total", 0) + 1
        save_progress(progress)

        # Mark completion in CSV (only for CSV queries, not --query)
        if not args.query:
            mark_query_completed(RESEARCH_LIST, query_info['index'], result['status'])

        # Print result
        status_emoji = "✓" if result["status"] in ["success", "partial_success"] else "✗"
        print(f"    {status_emoji} Status: {result['status']}")
        print(f"    Found: {result['videos_found']} | Downloaded: {result['videos_downloaded']} | Processed: {result['videos_processed']} | Uploaded: {result['videos_uploaded']}")
        if result.get("videos_failed", 0) > 0:
            print(f"    Failed: {result['videos_failed']}")
        if result.get("space_freed_mb", 0) > 0:
            print(f"    Space freed: {result['space_freed_mb']}MB")
        if result.get("errors"):
            for err in result["errors"][:2]:
                print(f"    Error: {err[:80]}")
        print()

        # Random wait between queries to avoid rate limiting (except for last query)
        if i < len(queries):
            random_wait(MIN_WAIT_BETWEEN_QUERIES, MAX_WAIT_BETWEEN_QUERIES, "between queries")

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    success = sum(1 for r in results if r["status"] in ["success", "partial_success"])
    partial = sum(1 for r in results if r["status"] == "partial_success")
    failed = sum(1 for r in results if r["status"] not in ["success", "partial_success", "dry_run"])
    total_uploaded = sum(r["videos_uploaded"] for r in results)
    total_failed_videos = sum(r.get("videos_failed", 0) for r in results)

    print(f"Queries processed: {len(results)}")
    print(f"Successful: {success} ({partial} partial)")
    print(f"Failed: {failed}")
    print(f"Total videos uploaded: {total_uploaded}")
    if total_failed_videos > 0:
        print(f"Total videos failed: {total_failed_videos}")
    if total_space_freed > 0:
        print(f"Total space freed: {total_space_freed:.1f}MB")

    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info(f"Queries: {len(results)}, Success: {success}, Failed: {failed}")
    logger.info(f"Videos uploaded: {total_uploaded}, Videos failed: {total_failed_videos}")
    logger.info(f"Space freed: {total_space_freed:.1f}MB")

    if FAILURES_FILE.exists():
        print(f"\nFailure log: {FAILURES_FILE}")

    print(f"Full log: {LOG_DIR / 'latest.log'}")


if __name__ == "__main__":
    main()
