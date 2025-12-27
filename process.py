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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import cv2
import httpx
import numpy as np

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')


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


def process_video(work_dir: Path, whisper_model: str = "base") -> dict:
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

    # OCR on frames (batched + parallel)
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


def watch_and_process(output_dir: Path, whisper_model: str = "base", interval: float = 5.0):
    """Watch for new downloads and process them."""
    print(f"=== Watching for new videos ===")
    print(f"Directory: {output_dir}")
    print(f"Press Ctrl+C to stop")
    print()

    processed = set()

    while True:
        unprocessed = find_unprocessed(output_dir)
        new_dirs = [d for d in unprocessed if str(d) not in processed]

        for work_dir in new_dirs:
            print(f"\nProcessing: {work_dir.name}")
            result = process_video(work_dir, whisper_model)

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
            watch_and_process(output_dir, args.model)
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
    print()

    # Process each directory
    successful = 0
    failed = 0
    total_time = 0

    for i, work_dir in enumerate(work_dirs, 1):
        # Skip already processed unless --reprocess
        if not args.reprocess and is_processed(work_dir):
            print(f"[{i}/{len(work_dirs)}] {work_dir.name} - already processed, skipping")
            continue

        print(f"[{i}/{len(work_dirs)}] {work_dir.name}")

        result = process_video(work_dir, args.model)

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
