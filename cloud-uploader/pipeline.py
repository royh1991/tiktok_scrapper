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
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / '.env')

# Configuration
BASE_DIR = Path(__file__).parent.parent
RESEARCH_LIST = BASE_DIR / "research_list.csv"
OUTPUT_DIR = BASE_DIR / "output"
PROGRESS_FILE = BASE_DIR / "cloud-uploader" / "progress.json"
FAILURES_FILE = BASE_DIR / "cloud-uploader" / "failures.json"

# Retry configuration
MAX_SEARCH_RETRIES = 3
MAX_DOWNLOAD_RETRIES = 2
MAX_PROCESS_RETRIES = 3
MAX_UPLOAD_RETRIES = 3
RETRY_DELAY_BASE = 2  # seconds, doubles each retry

# Import search function
from tiktok_search import google_search


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

    last_error = None
    for attempt in range(MAX_SEARCH_RETRIES):
        try:
            result = asyncio.run(google_search(query, num_results=max_results))
            urls = result.get('urls', [])
            print(f"        Found {len(urls)} videos")
            return urls
        except Exception as e:
            last_error = str(e)
            if attempt < MAX_SEARCH_RETRIES - 1:
                delay = RETRY_DELAY_BASE * (2 ** attempt)
                print(f"        Search failed (attempt {attempt + 1}/{MAX_SEARCH_RETRIES}): {e}")
                print(f"        Retrying in {delay}s...")
                time.sleep(delay)
            else:
                print(f"        Search failed after {MAX_SEARCH_RETRIES} attempts: {e}")

    if query_info:
        log_failure("search", query_info, last_error)
    return []


def run_download_with_retry(urls: list[str], output_dir: Path, workers: int = 3, query_info: dict = None) -> tuple[int, list[str]]:
    """
    Run TikTok downloader with retry logic.

    Returns (downloaded_count, failed_urls).
    """
    if not urls:
        return 0, []

    print(f"  [2/4] Downloading {len(urls)} videos...")

    output_dir.mkdir(parents=True, exist_ok=True)

    all_failed_urls = []
    total_downloaded = 0
    urls_to_try = urls.copy()

    for attempt in range(MAX_DOWNLOAD_RETRIES):
        if not urls_to_try:
            break

        # Write URLs to temp file
        temp_urls = output_dir / "temp_urls.txt"
        with open(temp_urls, 'w') as f:
            f.write('\n'.join(urls_to_try))

        try:
            cmd = [
                sys.executable, str(BASE_DIR / "tiktok_downloader.py"),
                "--workers", str(workers),
                "-o", str(output_dir),
                "download", "--file", str(temp_urls),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            # Count downloaded videos
            downloaded_dirs = [d for d in output_dir.iterdir() if d.is_dir() and (d / "video.mp4").exists()]
            downloaded_ids = {d.name for d in downloaded_dirs}

            current_downloaded = len(downloaded_dirs)

            if attempt == 0:
                total_downloaded = current_downloaded
                print(f"        Downloaded {current_downloaded}/{len(urls)} videos")
            else:
                new_downloads = current_downloaded - total_downloaded
                total_downloaded = current_downloaded
                print(f"        Retry {attempt}: Downloaded {new_downloads} more videos (total: {total_downloaded})")

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

            if not failed_urls:
                break

            urls_to_try = failed_urls

            if attempt < MAX_DOWNLOAD_RETRIES - 1 and failed_urls:
                delay = RETRY_DELAY_BASE * (2 ** attempt)
                print(f"        {len(failed_urls)} failed, retrying in {delay}s...")
                time.sleep(delay)

        except subprocess.TimeoutExpired:
            print(f"        Download timed out (attempt {attempt + 1})")
            if attempt < MAX_DOWNLOAD_RETRIES - 1:
                time.sleep(RETRY_DELAY_BASE)
        except Exception as e:
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


def run_process_single_video(video_dir: Path, whisper_model: str = "base") -> bool:
    """Process a single video with retry logic."""
    for attempt in range(MAX_PROCESS_RETRIES):
        try:
            cmd = [
                sys.executable, str(BASE_DIR / "process.py"),
                str(video_dir),
                "--model", whisper_model,
            ]

            if attempt > 0:
                cmd.append("--reprocess")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            # Check if processing succeeded
            has_transcript = (video_dir / "transcript.txt").exists()
            has_ocr = (video_dir / "ocr.json").exists()
            has_audio = (video_dir / "audio.mp3").exists()

            if has_transcript and has_ocr and has_audio:
                # Validate transcript has content
                content = (video_dir / "transcript.txt").read_text().strip()
                if len(content) >= 3:
                    return True

            if attempt < MAX_PROCESS_RETRIES - 1:
                delay = RETRY_DELAY_BASE * (2 ** attempt)
                time.sleep(delay)

        except subprocess.TimeoutExpired:
            if attempt < MAX_PROCESS_RETRIES - 1:
                time.sleep(RETRY_DELAY_BASE)
        except Exception:
            if attempt < MAX_PROCESS_RETRIES - 1:
                time.sleep(RETRY_DELAY_BASE)

    return False


def run_process_with_retry(output_dir: Path, whisper_model: str = "base", query_info: dict = None) -> tuple[int, int]:
    """
    Run video processing with per-video retry logic.

    Returns (processed_count, failed_count).
    """
    video_dirs = [d for d in output_dir.iterdir() if d.is_dir() and (d / "video.mp4").exists()]

    if not video_dirs:
        return 0, 0

    # Find unprocessed videos
    unprocessed = []
    already_processed = 0

    for d in video_dirs:
        has_transcript = (d / "transcript.txt").exists()
        has_ocr = (d / "ocr.json").exists()
        has_audio = (d / "audio.mp3").exists()

        if has_transcript and has_ocr and has_audio:
            # Validate transcript
            try:
                content = (d / "transcript.txt").read_text().strip()
                if len(content) >= 3:
                    already_processed += 1
                    continue
            except:
                pass

        unprocessed.append(d)

    if not unprocessed:
        print(f"  [3/4] All {len(video_dirs)} videos already processed")
        return len(video_dirs), 0

    print(f"  [3/4] Processing {len(unprocessed)} videos...")

    # First, try batch processing
    try:
        cmd = [
            sys.executable, str(BASE_DIR / "process.py"),
            "--output", str(output_dir),
            "--model", whisper_model,
        ]
        subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except:
        pass

    # Now check which ones failed and retry individually
    processed = already_processed
    failed = 0
    failed_dirs = []

    for video_dir in unprocessed:
        has_transcript = (video_dir / "transcript.txt").exists()
        has_ocr = (video_dir / "ocr.json").exists()
        has_audio = (video_dir / "audio.mp3").exists()

        if has_transcript and has_ocr and has_audio:
            try:
                content = (video_dir / "transcript.txt").read_text().strip()
                if len(content) >= 3:
                    processed += 1
                    continue
            except:
                pass

        # Try individual processing with retries
        print(f"        Retrying {video_dir.name}...")
        if run_process_single_video(video_dir, whisper_model):
            processed += 1
        else:
            failed += 1
            failed_dirs.append(video_dir.name)

    print(f"        Processed: {processed}, Failed: {failed}")

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

        # Check transcript
        transcript_path = video_dir / "transcript.txt"
        if not transcript_path.exists():
            is_valid = False
        else:
            try:
                content = transcript_path.read_text().strip()
                if not content or len(content) < 3:
                    is_valid = False
            except:
                is_valid = False

        # Check OCR
        ocr_path = video_dir / "ocr.json"
        if not ocr_path.exists():
            is_valid = False
        else:
            try:
                with open(ocr_path) as f:
                    ocr_data = json.load(f)
            except json.JSONDecodeError:
                is_valid = False

        # Check audio
        audio_path = video_dir / "audio.mp3"
        if not audio_path.exists():
            is_valid = False

        if is_valid:
            valid.append(video_dir)
        else:
            invalid.append(video_dir)

    return valid, invalid


def run_upload_with_retry(output_dir: Path, dry_run: bool = False, query_info: dict = None) -> tuple[int, int]:
    """
    Upload processed videos with retry logic.

    Returns (uploaded_count, failed_count).
    """
    valid_dirs, _ = validate_processing(output_dir)

    if not valid_dirs:
        return 0, 0

    print(f"  [4/4] Uploading {len(valid_dirs)} videos...")

    last_error = None
    for attempt in range(MAX_UPLOAD_RETRIES):
        try:
            cmd = [
                sys.executable, str(BASE_DIR / "cloud-uploader" / "upload.py"),
                "--output-dir", str(output_dir),
            ]

            if dry_run:
                cmd.append("--dry-run")

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
                if failed > 0:
                    print(f"        Failed: {failed}")
                return uploaded, failed

            # If no uploads, might be an error
            if attempt < MAX_UPLOAD_RETRIES - 1:
                delay = RETRY_DELAY_BASE * (2 ** attempt)
                print(f"        Upload may have failed, retrying in {delay}s...")
                time.sleep(delay)

            last_error = result.stderr[:200] if result.stderr else "Unknown error"

        except subprocess.TimeoutExpired:
            last_error = "Upload timed out"
            if attempt < MAX_UPLOAD_RETRIES - 1:
                delay = RETRY_DELAY_BASE * (2 ** attempt)
                print(f"        Upload timed out, retrying in {delay}s...")
                time.sleep(delay)
        except Exception as e:
            last_error = str(e)
            if attempt < MAX_UPLOAD_RETRIES - 1:
                delay = RETRY_DELAY_BASE * (2 ** attempt)
                print(f"        Upload error: {e}, retrying in {delay}s...")
                time.sleep(delay)

    print(f"        Upload failed after {MAX_UPLOAD_RETRIES} attempts")
    if query_info:
        log_failure("upload", query_info, last_error)

    return 0, len(valid_dirs)


def process_query(
    query_info: dict,
    max_results: int = 20,
    workers: int = 3,
    whisper_model: str = "base",
    dry_run: bool = False,
) -> dict:
    """
    Process a single query through the full pipeline with retry logic.

    Returns a result dict with status and stats.
    """
    query = query_info['query']
    index = query_info['index']

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
            return result

        if dry_run:
            print(f"  [DRY RUN] Would download {len(urls)} videos")
            result["status"] = "dry_run"
            return result

        # Step 2: Download with retry
        downloaded, failed_urls = run_download_with_retry(urls, output_dir, workers, query_info)
        result["videos_downloaded"] = downloaded

        if downloaded == 0:
            result["status"] = "download_failed"
            result["errors"].append("No videos downloaded after retries")
            return result

        # Step 3: Process with per-video retry
        processed, process_failed = run_process_with_retry(output_dir, whisper_model, query_info)
        result["videos_processed"] = processed
        result["videos_failed"] += process_failed

        # Final validation
        valid, invalid = validate_processing(output_dir)
        result["videos_processed"] = len(valid)

        if len(valid) == 0:
            result["status"] = "processing_failed"
            result["errors"].append("No videos passed validation after retries")
            return result

        # Step 4: Upload with retry
        uploaded, upload_failed = run_upload_with_retry(output_dir, dry_run, query_info)
        result["videos_uploaded"] = uploaded
        result["videos_failed"] += upload_failed

        if uploaded == 0 and len(valid) > 0:
            result["status"] = "upload_failed"
            result["errors"].append("Upload failed after retries")
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
        return result

    except Exception as e:
        result["status"] = "error"
        result["errors"].append(str(e))
        log_failure("pipeline", query_info, str(e), {"traceback": traceback.format_exc()})
        return result


def main():
    parser = argparse.ArgumentParser(description="TikTok Research Pipeline")
    parser.add_argument("--start", type=int, default=0, help="Starting query index")
    parser.add_argument("--count", type=int, help="Number of queries to process")
    parser.add_argument("--query", help="Process a specific query instead of CSV")
    parser.add_argument("--max-results", type=int, default=20, help="Max videos per query")
    parser.add_argument("--workers", type=int, default=3, help="Browser workers for download")
    parser.add_argument("--whisper-model", default="base", help="Whisper model for transcription")
    parser.add_argument("--dry-run", action="store_true", help="Search only, don't download")
    parser.add_argument("--resume", action="store_true", help="Skip already processed queries")

    args = parser.parse_args()

    print("=" * 60)
    print("TikTok Research Pipeline")
    print("=" * 60)

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
            sys.exit(1)

        queries = load_queries(RESEARCH_LIST, args.start, args.count)

    print(f"Queries to process: {len(queries)}")
    print(f"Max results per query: {args.max_results}")
    print(f"Workers: {args.workers}")
    print(f"Whisper model: {args.whisper_model}")
    print(f"Retry config: search={MAX_SEARCH_RETRIES}, download={MAX_DOWNLOAD_RETRIES}, process={MAX_PROCESS_RETRIES}, upload={MAX_UPLOAD_RETRIES}")
    if args.dry_run:
        print("Mode: DRY RUN")
    if args.resume:
        print(f"Resume: Skipping {len(processed_set)} already processed")
    print("=" * 60)
    print()

    # Process each query
    results = []

    for i, query_info in enumerate(queries, 1):
        query_key = f"{query_info['index']}:{query_info['query']}"

        if args.resume and query_key in processed_set:
            print(f"[{i}/{len(queries)}] Skipping (already processed): {query_info['query'][:50]}")
            continue

        print(f"[{i}/{len(queries)}] {query_info['city']}, {query_info['country']}")
        print(f"    Query: {query_info['query'][:60]}...")

        result = process_query(
            query_info,
            max_results=args.max_results,
            workers=args.workers,
            whisper_model=args.whisper_model,
            dry_run=args.dry_run,
        )

        results.append(result)

        # Update progress
        if result["status"] in ["success", "partial_success"]:
            progress["processed_queries"].append(query_key)
            progress["stats"]["success"] = progress["stats"].get("success", 0) + 1
        else:
            progress["stats"]["failed"] = progress["stats"].get("failed", 0) + 1

        progress["stats"]["total"] = progress["stats"].get("total", 0) + 1
        save_progress(progress)

        # Print result
        status_emoji = "✓" if result["status"] in ["success", "partial_success"] else "✗"
        print(f"    {status_emoji} Status: {result['status']}")
        print(f"    Found: {result['videos_found']} | Downloaded: {result['videos_downloaded']} | Processed: {result['videos_processed']} | Uploaded: {result['videos_uploaded']}")
        if result.get("videos_failed", 0) > 0:
            print(f"    Failed: {result['videos_failed']}")
        if result.get("errors"):
            for err in result["errors"][:2]:
                print(f"    Error: {err[:80]}")
        print()

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

    if FAILURES_FILE.exists():
        print(f"\nFailure log: {FAILURES_FILE}")


if __name__ == "__main__":
    main()
