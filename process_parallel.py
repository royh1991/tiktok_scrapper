#!/usr/bin/env python3
"""
TikTok Video Processor - Parallel Version

Processes multiple videos in parallel with memory-aware worker allocation.

Usage:
    python process_parallel.py --trip la-hidden-gems-vgvn --model tiny
    python process_parallel.py --output ./output --model base --workers 4
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
from pathlib import Path

import cv2
import httpx
import numpy as np

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

# Approximate RAM usage per Whisper model (GB)
WHISPER_RAM_USAGE = {
    "tiny": 1.0,
    "base": 1.5,
    "small": 2.5,
    "medium": 5.0,
    "large": 10.0,
}

AVAILABLE_RAM_GB = 8.0
RAM_BUFFER_GB = 2.0  # Reserve for system + OpenCV + other overhead


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
    """Extract unique scene frames from video using scene detection."""
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
    return frames, duration


# ============================================================
# Batched OCR with Claude Haiku
# ============================================================

def frame_to_base64(frame, max_size=384):
    """Resize and convert frame to base64 JPEG."""
    h, w = frame.shape[:2]
    if max(h, w) > max_size:
        scale = max_size / max(h, w)
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
    return base64.standard_b64encode(buffer).decode('utf-8')


def ocr_batch(frames, batch_id: int = 0):
    """Send a batch of frames to Claude in one API call."""
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


def ocr_frames_batched(frames: list, output_path: Path, batch_size: int = 50) -> dict:
    """Run OCR on frames using batched API calls."""
    if not frames:
        return {"items": [], "scenes": 0}

    if not ANTHROPIC_API_KEY:
        return {"items": [], "scenes": len(frames)}

    batches = []
    for i in range(0, len(frames), batch_size):
        batches.append((i // batch_size, frames[i:i + batch_size]))

    all_items = []
    for batch_id, batch in batches:
        try:
            items = ocr_batch(batch, batch_id)
            all_items.extend(items)
        except Exception as e:
            pass  # Silent fail for batches

    # Deduplicate
    seen = set()
    unique_items = []
    for item in all_items:
        item_lower = item.lower().strip()
        if item_lower not in seen:
            seen.add(item_lower)
            unique_items.append(item)

    result = {"scenes": len(frames), "items": unique_items}
    output_path.write_text(json.dumps(result, indent=2))
    return result


# ============================================================
# Audio Extraction & Transcription
# ============================================================

def extract_audio(video_path: Path, audio_path: Path) -> None:
    """Extract audio from video."""
    run_cmd([
        "ffmpeg", "-i", str(video_path),
        "-vn", "-acodec", "mp3", "-q:a", "4",
        str(audio_path), "-y"
    ])


def transcribe_audio(audio_path: Path, output_dir: Path, model: str = "base") -> str:
    """Transcribe audio using Whisper."""
    import whisper

    model_obj = whisper.load_model(model)
    result = model_obj.transcribe(str(audio_path))

    transcript_path = output_dir / "transcript.txt"
    transcript_path.write_text(result["text"].strip())

    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"].strip(),
        })

    timestamps_path = output_dir / "transcript_timestamps.json"
    timestamps_path.write_text(json.dumps(segments, indent=2))

    return result["text"].strip()


# ============================================================
# Single Video Processing (runs in worker process)
# ============================================================

def process_single_video(args: tuple) -> dict:
    """Process a single video. Designed to run in a separate process."""
    work_dir, whisper_model, video_idx, total_videos = args
    work_dir = Path(work_dir)

    video_name = work_dir.name
    prefix = f"[{video_idx}/{total_videos}] {video_name}"

    # Find video file
    video_path = work_dir / "video.mp4"
    if not video_path.exists():
        video_path = work_dir / "video.webm"
    if not video_path.exists():
        return {"success": False, "error": "No video file", "name": video_name}

    frames_dir = work_dir / "frames"
    audio_path = work_dir / "audio.mp3"
    ocr_path = work_dir / "ocr.json"

    start_time = time.time()

    try:
        # 1. Extract frames
        frames, duration = extract_scene_frames(video_path, frames_dir)

        # 2. Extract audio
        extract_audio(video_path, audio_path)

        # 3. OCR
        ocr_results = ocr_frames_batched(frames, ocr_path)

        # 4. Transcribe
        transcript = transcribe_audio(audio_path, work_dir, whisper_model)

        total_time = time.time() - start_time

        return {
            "success": True,
            "name": video_name,
            "work_dir": str(work_dir),
            "duration": duration,
            "scenes": len(frames),
            "ocr_items": len(ocr_results.get("items", [])),
            "transcript_length": len(transcript),
            "processing_time": round(total_time, 1),
        }

    except Exception as e:
        return {"success": False, "error": str(e), "name": video_name}


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


def find_unprocessed(output_dir: Path) -> list[Path]:
    """Find all work directories that need processing."""
    dirs = []
    for item in output_dir.iterdir():
        if item.is_dir() and needs_processing(item):
            dirs.append(item)
    return sorted(dirs)


def find_all_videos(output_dir: Path) -> list[Path]:
    """Find all work directories with videos."""
    dirs = []
    for item in output_dir.iterdir():
        if item.is_dir():
            has_video = (item / "video.mp4").exists() or (item / "video.webm").exists()
            if has_video:
                dirs.append(item)
    return sorted(dirs)


def calculate_max_workers(model: str, available_ram: float = AVAILABLE_RAM_GB) -> int:
    """Calculate max parallel workers based on model RAM usage."""
    model_ram = WHISPER_RAM_USAGE.get(model, 2.0)
    usable_ram = available_ram - RAM_BUFFER_GB
    max_by_ram = max(1, int(usable_ram / model_ram))
    max_by_cpu = max(1, cpu_count() - 1)
    return min(max_by_ram, max_by_cpu)


def main():
    parser = argparse.ArgumentParser(description="Process TikTok videos in parallel")
    parser.add_argument("dirs", nargs="*", type=Path, help="Specific directories to process")
    parser.add_argument("--trip", help="Trip ID (processes trips/{trip_id}/videos/)")
    parser.add_argument("-o", "--output", type=Path, default=Path(__file__).parent / "output",
                        help="Output directory to scan")
    parser.add_argument("-m", "--model", default="base", choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper model (default: base)")
    parser.add_argument("-w", "--workers", type=int, default=None,
                        help="Number of parallel workers (auto-calculated if not set)")
    parser.add_argument("--reprocess", action="store_true",
                        help="Reprocess already processed directories")
    parser.add_argument("--ram", type=float, default=AVAILABLE_RAM_GB,
                        help=f"Available RAM in GB (default: {AVAILABLE_RAM_GB})")

    args = parser.parse_args()

    # Determine output directory
    trip_dir = None
    if args.trip:
        base_dir = Path(__file__).parent
        trip_dir = base_dir / "trips" / args.trip
        output_dir = trip_dir / "videos"
        print(f"Trip: {args.trip}")
    else:
        output_dir = args.output

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

    # Calculate workers
    if args.workers:
        max_workers = args.workers
    else:
        max_workers = calculate_max_workers(args.model, args.ram)

    print(f"=== TikTok Video Processor (Parallel) ===")
    print(f"Videos: {len(work_dirs)}")
    print(f"Workers: {max_workers} (model: {args.model}, ~{WHISPER_RAM_USAGE.get(args.model, 2)}GB each)")
    print(f"RAM: {args.ram}GB available")
    print()

    # Prepare tasks
    tasks = [
        (str(work_dir), args.model, i + 1, len(work_dirs))
        for i, work_dir in enumerate(work_dirs)
    ]

    # Process in parallel
    start_time = time.time()
    successful = 0
    failed = 0
    results = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {executor.submit(process_single_video, task): task for task in tasks}

        for future in as_completed(future_to_task):
            result = future.result()
            results.append(result)

            if result["success"]:
                successful += 1
                print(f"[{successful + failed}/{len(work_dirs)}] {result['name']}: "
                      f"{result['scenes']} scenes, {result['ocr_items']} OCR items, "
                      f"{result['processing_time']}s")
            else:
                failed += 1
                print(f"[{successful + failed}/{len(work_dirs)}] {result['name']}: "
                      f"FAILED - {result.get('error', 'Unknown error')}")

    total_time = time.time() - start_time

    # Summary
    print()
    print("=" * 50)
    print(f"Processed: {successful}/{len(work_dirs)}")
    print(f"Failed: {failed}")
    print(f"Total time: {total_time:.1f}s")
    if successful > 0:
        print(f"Avg per video: {total_time / successful:.1f}s")
        print(f"Throughput: {successful / (total_time / 60):.1f} videos/min")

    # Update trip metadata
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
