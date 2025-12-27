#!/usr/bin/env python3
"""
TikTok Video Processor

Processes downloaded videos: extracts frames via scene detection, runs batched OCR, transcribes audio.

Usage:
    python process.py                     # Process all unprocessed videos in output/
    python process.py output/7353240*/    # Process specific directories
    python process.py --watch             # Watch for new downloads and process them

Output structure:
    output/7353240544740429087/
    ├── video.mp4           # (from tiktok_downloader.py)
    ├── metadata.json       # (from tiktok_downloader.py)
    ├── audio.mp3           # Extracted audio
    ├── transcript.txt      # Whisper transcription
    ├── ocr.json            # OCR results {items: [...], scenes: N}
    └── frames/             # Scene frames (for debugging)
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import cv2
import httpx
import numpy as np

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

# Batch API settings
BATCH_API_POLL_INTERVAL = 5  # seconds between status checks
BATCH_API_MAX_WAIT = 600  # max seconds to wait for batch completion


def run_cmd(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


# ============================================================
# Frame Extraction with Scene Detection
# ============================================================

def is_scene_change(frame1, frame2, threshold=25):
    """Detect if two frames are from different scenes."""
    if frame1 is None:
        return True
    small1 = cv2.resize(frame1, (64, 64))
    small2 = cv2.resize(frame2, (64, 64))
    gray1 = cv2.cvtColor(small1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(small2, cv2.COLOR_BGR2GRAY)
    return np.mean(np.abs(gray1.astype(float) - gray2.astype(float))) > threshold


def extract_scene_frames(video_path: Path, frames_dir: Path, sample_interval: int = 15, scene_threshold: int = 25):
    """
    Extract unique scene frames from video using scene detection.

    Returns list of frame data dicts and video duration.
    """
    print(f"  [1/4] Extracting scene frames...")

    frames_dir.mkdir(parents=True, exist_ok=True)

    video = cv2.VideoCapture(str(video_path))
    fps = video.get(cv2.CAP_PROP_FPS)
    total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0

    prev = None
    frames = []
    frame_count = 0
    scene_num = 0

    while True:
        ret, frame = video.read()
        if not ret:
            break
        if frame_count % sample_interval == 0:
            if is_scene_change(prev, frame, scene_threshold):
                scene_num += 1
                time_sec = round(frame_count / fps, 1)

                # Save frame to disk
                filename = f"{scene_num:03d}_t{time_sec}s.jpg"
                frame_path = frames_dir / filename
                cv2.imwrite(str(frame_path), frame)

                frames.append({
                    'frame': frame_count,
                    'time': time_sec,
                    'scene': scene_num,
                    'image': frame.copy(),
                    'path': str(frame_path)
                })
                prev = frame.copy()
        frame_count += 1

    video.release()
    print(f"       {len(frames)} scenes detected ({duration:.1f}s video)")
    return frames, duration


# ============================================================
# Batched OCR with Claude Haiku (Parallelized)
# ============================================================

def frame_to_base64(frame, max_size=384):
    """Resize and convert frame to base64 JPEG."""
    h, w = frame.shape[:2]
    if max(h, w) > max_size:
        scale = max_size / max(h, w)
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
    return base64.standard_b64encode(buffer).decode('utf-8')


def ocr_batch(frames, batch_id: int = 0, max_retries: int = 3):
    """Send a batch of frames to Claude in one API call with retry logic."""
    content = []
    for f in frames:
        img_b64 = frame_to_base64(f['image'], max_size=384)
        content.append({
            'type': 'image',
            'source': {
                'type': 'base64',
                'media_type': 'image/jpeg',
                'data': img_b64
            }
        })

    content.append({
        'type': 'text',
        'text': '''These are frames from a TikTok video. Extract ALL visible text overlays.

Return a JSON array with one object per unique text item:
[{"text": "item name"}, {"text": "another item"}, ...]

Rules:
- Only include text overlays (titles, lists, captions)
- Ignore watermarks, usernames, UI elements
- Deduplicate - include each text only once
- Return ONLY the JSON array'''
    })

    last_error = None
    for attempt in range(max_retries):
        try:
            response = httpx.post(
                'https://api.anthropic.com/v1/messages',
                headers={
                    'x-api-key': ANTHROPIC_API_KEY,
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json',
                },
                json={
                    'model': 'claude-3-5-haiku-latest',
                    'max_tokens': 1000,
                    'messages': [{'role': 'user', 'content': content}]
                },
                timeout=90.0
            )

            if response.status_code == 429:
                # Rate limited - wait and retry
                retry_after = int(response.headers.get('retry-after', 2 ** attempt))
                time.sleep(retry_after)
                last_error = "Rate limited (429)"
                continue

            if response.status_code != 200:
                raise Exception(f"API error: {response.status_code}")

            result = response.json()
            text = result['content'][0]['text']

            try:
                items = json.loads(text)
                return [item['text'] for item in items if 'text' in item]
            except:
                import re
                return re.findall(r'"text":\s*"([^"]+)"', text)

        except httpx.TimeoutException:
            last_error = "Timeout"
            time.sleep(2 ** attempt)
            continue

    raise Exception(f"Failed after {max_retries} retries: {last_error}")


# ============================================================
# Batch API OCR (50% cheaper, async processing)
# ============================================================

def create_ocr_request(frames: list, request_id: str) -> dict:
    """Create a single batch request for a group of frames."""
    content = []
    for f in frames:
        img_b64 = frame_to_base64(f['image'], max_size=384)
        content.append({
            'type': 'image',
            'source': {
                'type': 'base64',
                'media_type': 'image/jpeg',
                'data': img_b64
            }
        })

    content.append({
        'type': 'text',
        'text': '''These are frames from a TikTok video. Extract ALL visible text overlays.

Return a JSON array with one object per unique text item:
[{"text": "item name"}, {"text": "another item"}, ...]

Rules:
- Only include text overlays (titles, lists, captions)
- Ignore watermarks, usernames, UI elements
- Deduplicate - include each text only once
- Return ONLY the JSON array'''
    })

    return {
        'custom_id': request_id,
        'params': {
            'model': 'claude-3-5-haiku-latest',
            'max_tokens': 1000,
            'messages': [{'role': 'user', 'content': content}]
        }
    }


def submit_batch(requests: list[dict]) -> str:
    """Submit a batch of requests to the Batch API. Returns batch_id."""
    response = httpx.post(
        'https://api.anthropic.com/v1/messages/batches',
        headers={
            'x-api-key': ANTHROPIC_API_KEY,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        },
        json={'requests': requests},
        timeout=120.0
    )

    if response.status_code != 200:
        raise Exception(f"Batch submit failed: {response.status_code} - {response.text}")

    result = response.json()
    return result['id']


def poll_batch_status(batch_id: str) -> dict:
    """Poll batch status until complete or timeout."""
    start_time = time.time()

    while True:
        elapsed = time.time() - start_time
        if elapsed > BATCH_API_MAX_WAIT:
            raise Exception(f"Batch {batch_id} timed out after {BATCH_API_MAX_WAIT}s")

        response = httpx.get(
            f'https://api.anthropic.com/v1/messages/batches/{batch_id}',
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
            },
            timeout=30.0
        )

        if response.status_code != 200:
            raise Exception(f"Batch status check failed: {response.status_code}")

        status = response.json()
        processing_status = status.get('processing_status')

        if processing_status == 'ended':
            return status

        # Show progress
        counts = status.get('request_counts', {})
        succeeded = counts.get('succeeded', 0)
        processing = counts.get('processing', 0)
        print(f"       Batch status: {processing} processing, {succeeded} done...", end='\r')

        time.sleep(BATCH_API_POLL_INTERVAL)


def retrieve_batch_results(batch_id: str) -> list[dict]:
    """Retrieve results from a completed batch."""
    response = httpx.get(
        f'https://api.anthropic.com/v1/messages/batches/{batch_id}/results',
        headers={
            'x-api-key': ANTHROPIC_API_KEY,
            'anthropic-version': '2023-06-01',
        },
        timeout=120.0
    )

    if response.status_code != 200:
        raise Exception(f"Batch results retrieval failed: {response.status_code}")

    # Results come as newline-delimited JSON
    results = []
    for line in response.text.strip().split('\n'):
        if line:
            results.append(json.loads(line))

    return results


def parse_ocr_response(text: str) -> list[str]:
    """Parse OCR response text into list of items."""
    try:
        items = json.loads(text)
        return [item['text'] for item in items if 'text' in item]
    except:
        import re
        return re.findall(r'"text":\s*"([^"]+)"', text)


def ocr_frames_batch_api(frames: list, output_path: Path, batch_size: int = 50) -> dict:
    """
    Run OCR on frames using the Batch API (50% cheaper).

    Args:
        frames: List of frame dicts with 'image' key
        output_path: Path to save ocr.json
        batch_size: Frames per request (default 50)
    """
    print(f"  [3/4] Running OCR via Batch API ({len(frames)} frames)...")

    if not frames:
        return {"items": [], "scenes": 0}

    if not ANTHROPIC_API_KEY:
        print("       Warning: No ANTHROPIC_API_KEY, skipping OCR")
        return {"items": [], "scenes": len(frames)}

    # Create batch requests
    requests = []
    for i in range(0, len(frames), batch_size):
        batch_frames = frames[i:i + batch_size]
        request_id = f"ocr_{i//batch_size}_{uuid.uuid4().hex[:8]}"
        requests.append(create_ocr_request(batch_frames, request_id))

    print(f"       Submitting {len(requests)} request(s) to Batch API...")

    try:
        # Submit batch
        batch_id = submit_batch(requests)
        print(f"       Batch ID: {batch_id}")

        # Poll for completion
        status = poll_batch_status(batch_id)
        print()  # Clear the status line

        counts = status.get('request_counts', {})
        print(f"       Batch complete: {counts.get('succeeded', 0)} succeeded, {counts.get('errored', 0)} failed")

        # Retrieve results
        results = retrieve_batch_results(batch_id)

        # Parse all OCR items
        all_items = []
        for result in results:
            if result.get('result', {}).get('type') == 'succeeded':
                message = result['result']['message']
                text = message['content'][0]['text']
                items = parse_ocr_response(text)
                all_items.extend(items)

    except Exception as e:
        print(f"       Batch API error: {e}")
        print("       Falling back to real-time API...")
        return ocr_frames_batched(frames, output_path, batch_size, max_workers=2)

    # Deduplicate while preserving order
    seen = set()
    unique_items = []
    for item in all_items:
        item_lower = item.lower().strip()
        if item_lower not in seen:
            seen.add(item_lower)
            unique_items.append(item)

    result = {
        "scenes": len(frames),
        "items": unique_items
    }

    # Save results
    output_path.write_text(json.dumps(result, indent=2))
    print(f"       Found {len(unique_items)} unique text items (50% cost savings!)")

    return result


# ============================================================
# Claude Code CLI OCR (uses Claude subscription, not API credits)
# ============================================================

def ocr_with_claude_code(frame_paths: list[str], max_retries: int = 3) -> dict:
    """Run OCR using Claude Code CLI with Haiku model. Returns {items: [...], description: "..."}."""
    import subprocess
    import re

    # Build prompt with file paths for Claude Code to read
    files_list = '\n'.join(frame_paths)
    prompt = f"""Read these image files and extract ALL visible text overlays:

{files_list}

Return ONLY valid JSON with this exact structure, no other text:
{{
  "items": ["text item 1", "text item 2"],
  "description": "Brief description of what's happening in the video (1-2 sentences)"
}}

Rules for items:
- Only include text overlays (titles, lists, captions)
- Ignore watermarks, usernames, UI elements
- Deduplicate - include each text only once
- Return empty array [] if no text found

Rules for description:
- Describe the visual content and what the video shows
- Keep it concise (1-2 sentences)
- Focus on the main subject/activity"""

    for attempt in range(max_retries):
        try:
            # Use Haiku model for fast, cheap OCR (not the user's default model)
            result = subprocess.run(
                ['claude', '-p', prompt, '--output-format', 'text', '--model', 'claude-3-5-haiku-latest'],
                capture_output=True,
                text=True,
                timeout=180
            )

            if result.returncode != 0:
                raise Exception(f"Claude Code error: {result.stderr}")

            output = result.stdout.strip()

            # Extract JSON object from output
            json_match = re.search(r'\{[^{}]*"items"[^{}]*\}', output, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    "items": data.get("items", []),
                    "description": data.get("description", "")
                }

            # Fallback: try to parse the whole output as JSON
            try:
                data = json.loads(output)
                return {
                    "items": data.get("items", []),
                    "description": data.get("description", "")
                }
            except:
                pass

            # Last resort: regex extraction
            items = re.findall(r'"text":\s*"([^"]+)"', output)
            return {"items": items, "description": ""}

        except subprocess.TimeoutExpired:
            print(f"       Attempt {attempt + 1} timed out, retrying...")
        except json.JSONDecodeError as e:
            print(f"       Attempt {attempt + 1} JSON parse error: {e}")
        except Exception as e:
            print(f"       Attempt {attempt + 1} failed: {e}")

        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)

    return {"items": [], "description": ""}


def ocr_frames_claude_code(frames: list, output_path: Path) -> dict:
    """Run OCR using Claude Code CLI (uses subscription, not API credits)."""
    print(f"  [3/4] Running OCR via Claude Code ({len(frames)} frames)...")

    if not frames:
        return {"items": [], "scenes": 0, "description": ""}

    # Get frame paths
    frame_paths = [f['path'] for f in frames]

    # Call Claude Code
    result = ocr_with_claude_code(frame_paths)
    items = result.get("items", [])
    description = result.get("description", "")

    # Deduplicate items while preserving order
    seen = set()
    unique_items = []
    for item in items:
        item_lower = item.lower().strip()
        if item_lower not in seen:
            seen.add(item_lower)
            unique_items.append(item)

    output_data = {
        "scenes": len(frames),
        "items": unique_items,
        "description": description
    }

    output_path.write_text(json.dumps(output_data, indent=2))
    print(f"       Found {len(unique_items)} unique text items")
    if description:
        print(f"       Description: {description[:60]}...")

    return output_data


def ocr_frames_batched(frames: list, output_path: Path, batch_size: int = 50, max_workers: int = 2) -> dict:
    """
    Run OCR on frames using batched parallel API calls.

    Args:
        frames: List of frame dicts with 'image' key
        output_path: Path to save ocr.json
        batch_size: Frames per API call (default 50)
        max_workers: Parallel API calls (default 4)
    """
    print(f"  [3/4] Running batched OCR ({len(frames)} frames, {max_workers} parallel)...")

    if not frames:
        return {"items": [], "scenes": 0}

    if not ANTHROPIC_API_KEY:
        print("       Warning: No ANTHROPIC_API_KEY, skipping OCR")
        return {"items": [], "scenes": len(frames)}

    # Split into batches
    batches = []
    for i in range(0, len(frames), batch_size):
        batches.append((i // batch_size, frames[i:i + batch_size]))

    all_items = []

    # Process batches in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(ocr_batch, batch, batch_id): batch_id
                   for batch_id, batch in batches}

        for future in as_completed(futures):
            batch_id = futures[future]
            try:
                items = future.result()
                all_items.extend(items)
                print(f"       Batch {batch_id + 1}/{len(batches)} done ({len(items)} items)")
            except Exception as e:
                print(f"       Batch {batch_id + 1}/{len(batches)} failed: {e}")

    # Deduplicate while preserving order
    seen = set()
    unique_items = []
    for item in all_items:
        item_lower = item.lower().strip()
        if item_lower not in seen:
            seen.add(item_lower)
            unique_items.append(item)

    result = {
        "scenes": len(frames),
        "items": unique_items
    }

    # Save results
    output_path.write_text(json.dumps(result, indent=2))
    print(f"       Found {len(unique_items)} unique text items")

    return result


# ============================================================
# Audio Extraction & Transcription
# ============================================================

def extract_audio(video_path: Path, audio_path: Path) -> None:
    """Extract audio from video."""
    print(f"  [2/4] Extracting audio...")
    run_cmd([
        "ffmpeg", "-i", str(video_path),
        "-vn", "-acodec", "mp3", "-q:a", "4",
        str(audio_path), "-y"
    ])
    print(f"       Audio extracted")


def transcribe_audio(audio_path: Path, output_dir: Path, model: str = "base") -> str:
    """Transcribe audio using Whisper."""
    print(f"  [4/4] Transcribing with Whisper ({model})...")

    import whisper

    model_obj = whisper.load_model(model)
    result = model_obj.transcribe(str(audio_path))

    # Save transcription
    transcript_path = output_dir / "transcript.txt"
    transcript_path.write_text(result["text"].strip())

    # Save timestamps
    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"].strip(),
        })

    timestamps_path = output_dir / "transcript_timestamps.json"
    timestamps_path.write_text(json.dumps(segments, indent=2))

    print(f"       Transcribed {len(segments)} segments")
    return result["text"].strip()


# ============================================================
# Main Processing
# ============================================================

def is_processed(work_dir: Path) -> bool:
    """Check if a work directory has already been processed."""
    return (work_dir / "transcript.txt").exists() or (work_dir / "ocr.json").exists()


def needs_processing(work_dir: Path) -> bool:
    """Check if a work directory needs processing."""
    has_video = (work_dir / "video.mp4").exists() or (work_dir / "video.webm").exists()
    return has_video and not is_processed(work_dir)


def process_video(work_dir: Path, whisper_model: str = "base", use_batch_api: bool = False, use_claude_code: bool = False) -> dict:
    """Process a single video directory."""
    # Find video file
    video_path = work_dir / "video.mp4"
    if not video_path.exists():
        video_path = work_dir / "video.webm"
    if not video_path.exists():
        return {"success": False, "error": "No video file found"}

    frames_dir = work_dir / "frames"
    audio_path = work_dir / "audio.mp3"
    ocr_path = work_dir / "ocr.json"

    start_time = time.time()

    # Extract scene frames
    frames, duration = extract_scene_frames(video_path, frames_dir)

    # Extract audio
    extract_audio(video_path, audio_path)

    # OCR on frames (Claude Code CLI, batch API, or real-time parallel)
    if use_claude_code:
        ocr_results = ocr_frames_claude_code(frames, ocr_path)
    elif use_batch_api:
        ocr_results = ocr_frames_batch_api(frames, ocr_path)
    else:
        ocr_results = ocr_frames_batched(frames, ocr_path)

    # Transcribe audio
    transcript = transcribe_audio(audio_path, work_dir, whisper_model)

    total_time = time.time() - start_time

    return {
        "success": True,
        "work_dir": str(work_dir),
        "duration": duration,
        "scenes": len(frames),
        "ocr_items": len(ocr_results.get("items", [])),
        "transcript_length": len(transcript),
        "processing_time": round(total_time, 1),
    }


def find_unprocessed(output_dir: Path) -> list[Path]:
    """Find all work directories that need processing."""
    dirs = []
    for item in output_dir.iterdir():
        if item.is_dir() and needs_processing(item):
            dirs.append(item)
    return sorted(dirs)


def find_all_videos(output_dir: Path) -> list[Path]:
    """Find all work directories with videos (for reprocessing)."""
    dirs = []
    for item in output_dir.iterdir():
        if item.is_dir():
            has_video = (item / "video.mp4").exists() or (item / "video.webm").exists()
            if has_video:
                dirs.append(item)
    return sorted(dirs)


def watch_and_process(output_dir: Path, whisper_model: str = "base", interval: float = 5.0, use_batch_api: bool = False, use_claude_code: bool = False):
    """Watch for new downloads and process them."""
    print(f"=== Watching for new videos ===")
    print(f"Directory: {output_dir}")
    if use_claude_code:
        print(f"OCR mode: Claude Code CLI (uses subscription)")
    elif use_batch_api:
        print(f"OCR mode: Batch API (50% savings)")
    else:
        print(f"OCR mode: Real-time API")
    print(f"Press Ctrl+C to stop")
    print()

    processed = set()

    while True:
        unprocessed = find_unprocessed(output_dir)
        new_dirs = [d for d in unprocessed if str(d) not in processed]

        for work_dir in new_dirs:
            print(f"\nProcessing: {work_dir.name}")
            result = process_video(work_dir, whisper_model, use_batch_api, use_claude_code)

            if result["success"]:
                print(f"  Done in {result['processing_time']}s: {result['scenes']} scenes, {result['ocr_items']} OCR items")
                processed.add(str(work_dir))
            else:
                print(f"  Error: {result.get('error')}")

        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Process downloaded TikTok videos")
    parser.add_argument("dirs", nargs="*", type=Path, help="Specific directories to process")
    parser.add_argument("--trip", help="Trip ID (processes trips/{trip_id}/videos/)")
    parser.add_argument("-o", "--output", type=Path, default=Path(__file__).parent / "output",
                        help="Output directory to scan (default: ./output)")
    parser.add_argument("-m", "--model", default="base", choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper model (default: base)")
    parser.add_argument("-w", "--watch", action="store_true",
                        help="Watch for new downloads and process them")
    parser.add_argument("--reprocess", action="store_true",
                        help="Reprocess already processed directories")
    parser.add_argument("--batch-ocr", action="store_true",
                        help="Use Batch API for OCR (50%% cheaper, but async)")
    parser.add_argument("--use-claude-code", action="store_true",
                        help="Use Claude Code CLI for OCR (uses subscription, not API credits)")
    parser.add_argument("--parallel", "-j", type=int, default=1,
                        help="Number of videos to process in parallel (default: 1)")

    args = parser.parse_args()

    # Determine output directory based on --trip
    trip_dir = None
    if args.trip:
        base_dir = Path(__file__).parent
        trip_dir = base_dir / "trips" / args.trip
        output_dir = trip_dir / "videos"
        print(f"Trip: {args.trip}")
    else:
        output_dir = args.output

    # Watch mode
    if args.watch:
        try:
            watch_and_process(output_dir, args.model, use_batch_api=args.batch_ocr, use_claude_code=args.use_claude_code)
        except KeyboardInterrupt:
            print("\nStopped")
        return

    # Get directories to process
    if args.dirs:
        work_dirs = [d for d in args.dirs if d.is_dir()]
    else:
        if not output_dir.exists():
            print(f"Error: Output directory not found: {output_dir}")
            sys.exit(1)
        if args.reprocess:
            work_dirs = find_all_videos(output_dir)
        else:
            work_dirs = find_unprocessed(output_dir)

    if not work_dirs:
        print("No videos to process")
        return

    print(f"=== TikTok Video Processor ===")
    print(f"Videos to process: {len(work_dirs)}")
    if args.use_claude_code:
        print(f"OCR mode: Claude Code CLI (Haiku model)")
    elif args.batch_ocr:
        print(f"OCR mode: Batch API (50% savings)")
    else:
        print(f"OCR mode: Real-time API")
    if args.parallel > 1:
        print(f"Parallel workers: {args.parallel}")
    print()

    # Filter out already processed unless --reprocess
    if not args.reprocess:
        to_process = [(i, d) for i, d in enumerate(work_dirs, 1) if not is_processed(d)]
        skipped = len(work_dirs) - len(to_process)
        if skipped > 0:
            print(f"Skipping {skipped} already processed videos")
    else:
        to_process = list(enumerate(work_dirs, 1))

    # Process videos (parallel or sequential)
    successful = 0
    failed = 0
    total_time = 0

    if args.parallel > 1 and len(to_process) > 1:
        # Parallel processing
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def process_one(item):
            i, work_dir = item
            result = process_video(work_dir, args.model, use_batch_api=args.batch_ocr, use_claude_code=args.use_claude_code)
            return i, work_dir, result

        with ThreadPoolExecutor(max_workers=args.parallel) as executor:
            futures = {executor.submit(process_one, item): item for item in to_process}

            for future in as_completed(futures):
                i, work_dir, result = future.result()
                if result["success"]:
                    print(f"[{i}/{len(work_dirs)}] {work_dir.name} - Done in {result['processing_time']}s: {result['scenes']} scenes, {result['ocr_items']} OCR items")
                    successful += 1
                    total_time += result['processing_time']
                else:
                    print(f"[{i}/{len(work_dirs)}] {work_dir.name} - Error: {result.get('error')}")
                    failed += 1
    else:
        # Sequential processing
        for i, work_dir in to_process:
            print(f"[{i}/{len(work_dirs)}] {work_dir.name}")

            result = process_video(work_dir, args.model, use_batch_api=args.batch_ocr, use_claude_code=args.use_claude_code)

            if result["success"]:
                print(f"  Done in {result['processing_time']}s: {result['scenes']} scenes, {result['ocr_items']} OCR items")
                successful += 1
                total_time += result['processing_time']
            else:
                print(f"  Error: {result.get('error')}")
                failed += 1

            print()

    # Summary
    print("=" * 40)
    print(f"Processed: {successful}")
    print(f"Failed: {failed}")
    if successful > 0:
        print(f"Total time: {total_time:.1f}s ({total_time/successful:.1f}s avg)")

    # Update trip metadata status
    if trip_dir:
        metadata_path = trip_dir / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path) as f:
                metadata = json.load(f)
            metadata["status"] = "processed"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            print(f"\nTrip status updated: processed")


if __name__ == "__main__":
    main()
