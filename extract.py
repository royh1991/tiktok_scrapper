#!/usr/bin/env python3
"""
TikTok Video Content Extractor

Downloads video, extracts frames, and transcribes audio.
Uses zendriver (undetectable Chrome automation) for downloads.

Usage:
    python extract.py <tiktok_url>
    python extract.py "url1,url2,url3"
    python extract.py --login              # Login to TikTok first

Dependencies (system):
    brew install ffmpeg
    # or on Linux: apt install ffmpeg xvfb

Environment:
    ANTHROPIC_API_KEY=your_api_key

Dependencies (python):
    pip install -r requirements.txt
"""

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import anthropic
import base64
from PIL import Image

from tiktok import TikTokDownloader, download_batch_parallel


def run_cmd(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def get_video_duration(video_path: Path) -> float:
    """Get video duration in seconds using ffprobe."""
    # Try format duration first
    result = run_cmd([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path)
    ], check=False)

    duration_str = result.stdout.strip()
    if duration_str and duration_str != "N/A":
        try:
            return float(duration_str)
        except ValueError:
            pass

    # Fallback: count frames and calculate from frame rate
    # This works for webm files without proper duration metadata
    result = run_cmd([
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-count_packets",
        "-show_entries", "stream=nb_read_packets,r_frame_rate",
        "-of", "csv=p=0",
        str(video_path)
    ], check=False)

    try:
        parts = result.stdout.strip().split(",")
        if len(parts) >= 2:
            # Parse frame rate (e.g., "30/1")
            fps_parts = parts[0].split("/")
            fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else float(fps_parts[0])
            frame_count = int(parts[1])
            return frame_count / fps
    except (ValueError, IndexError, ZeroDivisionError):
        pass

    # Last resort: estimate from file size (rough approximation)
    # Assume ~500KB per second for typical video
    file_size = video_path.stat().st_size
    return file_size / (500 * 1024)


def extract_frames(video_path: Path, frames_dir: Path, duration: float) -> int:
    """Extract frames from video. Returns frame count."""
    print(f"[2/5] Extracting frames...")

    frames_dir.mkdir(exist_ok=True)

    # Adjust FPS based on video length
    if duration < 30:
        fps = 2
    elif duration < 60:
        fps = 1
    else:
        fps = 0.5

    run_cmd([
        "ffmpeg", "-i", str(video_path),
        "-vf", f"fps={fps}",
        "-q:v", "2",
        str(frames_dir / "frame_%03d.jpg"),
        "-y"
    ])

    frame_count = len(list(frames_dir.glob("*.jpg")))
    print(f"✓ Extracted {frame_count} frames")
    return frame_count


def extract_audio(video_path: Path, audio_path: Path) -> None:
    """Extract audio from video."""
    print(f"[3/5] Extracting audio...")
    run_cmd([
        "ffmpeg", "-i", str(video_path),
        "-vn", "-acodec", "mp3", "-q:a", "4",
        str(audio_path), "-y"
    ])
    print(f"✓ Audio extracted")


def encode_image_base64(image_path: Path) -> str:
    """Encode image to base64 string."""
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def ocr_frames(frames_dir: Path, output_path: Path) -> dict[str, str]:
    """
    Extract text from frames using Claude vision.

    Returns dict mapping frame filename to extracted text.
    """
    print(f"[4/5] Extracting text from frames with Claude vision...")

    client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var
    results = {}
    frame_files = sorted(frames_dir.glob("*.jpg"))

    if not frame_files:
        print(f"✓ No frames to process")
        return results

    # Process frames in batches to reduce API calls
    batch_size = 5

    for i in range(0, len(frame_files), batch_size):
        batch = frame_files[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(frame_files) + batch_size - 1) // batch_size
        print(f"  Processing batch {batch_num}/{total_batches}...")

        # Build message content with multiple images
        content = []
        for frame_path in batch:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": encode_image_base64(frame_path),
                },
            })

        content.append({
            "type": "text",
            "text": f"""Extract ALL visible text from these {len(batch)} video frames.
This includes:
- Text overlays and captions
- Location tags
- Usernames and handles
- Product names, prices
- Any other on-screen text

For each frame, list the text found. If a frame has no text, say "No text".
Format your response as:
Frame 1: [text found]
Frame 2: [text found]
...

Be thorough - capture every piece of text you can see."""
        })

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": content}]
            )

            # Parse response and map to frame filenames
            response_text = response.content[0].text
            lines = response_text.strip().split("\n")

            frame_idx = 0
            current_text = []

            for line in lines:
                if line.lower().startswith("frame ") and ":" in line:
                    if current_text and frame_idx > 0:
                        text = "\n".join(current_text).strip()
                        if text.lower() != "no text" and text:
                            results[batch[frame_idx - 1].name] = text

                    frame_idx = int(line.split(":")[0].replace("Frame", "").replace("frame", "").strip())
                    text_after_colon = ":".join(line.split(":")[1:]).strip()
                    current_text = [text_after_colon] if text_after_colon else []
                else:
                    current_text.append(line)

            if current_text and frame_idx > 0 and frame_idx <= len(batch):
                text = "\n".join(current_text).strip()
                if text.lower() != "no text" and text:
                    results[batch[frame_idx - 1].name] = text

        except Exception as e:
            print(f"  Error processing batch: {e}")

    # Save results
    output_path.write_text(json.dumps(results, indent=2))

    # Also save deduplicated text summary
    unique_texts = list(set(results.values()))
    summary_path = output_path.parent / "ocr_summary.txt"
    summary_path.write_text("\n---\n".join(unique_texts))

    print(f"✓ Text extraction complete - found text in {len(results)}/{len(frame_files)} frames")
    return results


def transcribe_audio(audio_path: Path, output_dir: Path, model: str = "base") -> str:
    """Transcribe audio using Whisper. Returns transcription text."""
    print(f"[5/5] Transcribing audio (model: {model})...")

    import whisper

    model_obj = whisper.load_model(model)
    result = model_obj.transcribe(str(audio_path))

    # Save transcription
    transcript_path = output_dir / "transcript.txt"
    transcript_path.write_text(result["text"].strip())

    print(f"✓ Transcription complete")
    return result["text"].strip()


def process_video(video_path: Path, work_dir: Path, whisper_model: str, metadata: dict) -> dict:
    """Process a downloaded video: extract frames, OCR, transcribe."""
    frames_dir = work_dir / "frames"
    audio_path = work_dir / "audio.mp3"
    metadata_path = work_dir / "metadata.json"
    transcript_path = work_dir / "transcript.txt"
    ocr_path = work_dir / "ocr.json"

    # Save metadata
    metadata_path.write_text(json.dumps(metadata, indent=2))

    # Get duration
    duration = get_video_duration(video_path)
    print(f"Duration: {duration:.1f}s")
    print()

    # Extract frames
    frame_count = extract_frames(video_path, frames_dir, duration)
    print()

    # OCR on frames
    ocr_results = ocr_frames(frames_dir, ocr_path)
    print()

    # Extract and transcribe audio
    extract_audio(video_path, audio_path)
    transcript_text = transcribe_audio(audio_path, work_dir, whisper_model)
    print()

    # Summary
    print(f"=== Extraction Complete ===")
    print()
    print(f"Files created in {work_dir}/")
    print(f"  ├── video.webm       # Captured video")
    print(f"  ├── audio.mp3        # Extracted audio")
    print(f"  ├── transcript.txt   # Speech transcription")
    print(f"  ├── ocr.json         # Text from frames (per-frame)")
    print(f"  ├── ocr_summary.txt  # Text from frames (deduplicated)")
    print(f"  ├── metadata.json    # Video metadata")
    print(f"  └── frames/          # {frame_count} images")
    print()

    if transcript_text:
        print(f"Speech transcription:")
        print(f"  {transcript_text[:300]}{'...' if len(transcript_text) > 300 else ''}")
        print()

    if ocr_results:
        unique_ocr = list(set(ocr_results.values()))
        print(f"On-screen text ({len(unique_ocr)} unique):")
        for text in unique_ocr[:3]:
            preview = text[:100].replace('\n', ' ')
            print(f"  • {preview}{'...' if len(text) > 100 else ''}")
        if len(unique_ocr) > 3:
            print(f"  ... and {len(unique_ocr) - 3} more")
        print()

    return {
        "dir": work_dir,
        "video": video_path,
        "audio": audio_path,
        "frames": frames_dir,
        "transcript": transcript_path,
        "metadata": metadata_path,
        "ocr": ocr_path,
        "transcript_text": transcript_text,
        "ocr_results": ocr_results,
        "frame_count": frame_count,
        "duration": duration,
    }


async def extract_tiktok_async(
    url: str,
    downloader: TikTokDownloader,
    output_base: Path = None,
    whisper_model: str = "base"
) -> dict:
    """
    Main extraction pipeline (async version).

    Uses a shared TikTokDownloader instance for efficient batch processing.
    """
    # Setup output directory
    if output_base is None:
        output_base = Path(__file__).parent / "output"

    # Use timestamp + hash of URL for unique folder names
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    work_dir = output_base / f"{timestamp}_{url_hash}"
    work_dir.mkdir(parents=True, exist_ok=True)

    video_path = work_dir / "video.webm"

    print(f"=== TikTok Content Extractor ===")
    print(f"URL: {url}")
    print(f"Output: {work_dir}")
    print()

    # Step 1: Download video using zendriver (captures as webm)
    print(f"[1/5] Downloading video...")
    result = await downloader.download_video(url, video_path)

    if not result["success"]:
        raise Exception(f"Failed to download video: {result.get('error', 'Unknown error')}")

    # Get the actual video path (may have been changed to .webm)
    actual_video_path = result.get("video_path", video_path)

    # Process the video (sync operations)
    return process_video(actual_video_path, work_dir, whisper_model, result.get("metadata", {}))


async def extract_batch_async(
    urls: list[str],
    output_base: Path = None,
    whisper_model: str = "base",
    delay_between: float = 3.0,
    local: bool = False,
) -> list[dict]:
    """
    Extract content from multiple TikTok videos.

    Uses a single browser instance for all downloads to:
    1. Maintain login session
    2. Look more human-like
    3. Reduce resource usage

    Args:
        local: If True, auto-detect browser (for local dev). If False, use Docker paths.
    """
    if output_base is None:
        output_base = Path(__file__).parent / "output"

    output_base.mkdir(parents=True, exist_ok=True)

    print(f"=== TikTok Batch Extractor (zendriver) ===")
    print(f"Processing {len(urls)} videos")
    print(f"Output: {output_base}")
    print()

    results = []

    async with TikTokDownloader(local=local) as downloader:
        for i, url in enumerate(urls):
            url = url.strip()
            print(f"\n{'='*50}")
            print(f"[Video {i + 1}/{len(urls)}]")
            print(f"{'='*50}")

            try:
                result = await extract_tiktok_async(url, downloader, output_base, whisper_model)
                result["success"] = True
                result["url"] = url
                results.append(result)
            except Exception as e:
                print(f"Error: {e}")
                results.append({"success": False, "url": url, "error": str(e)})

            # Human-like delay between videos
            if i < len(urls) - 1:
                import random
                delay = delay_between + random.uniform(0, delay_between * 0.5)
                print(f"\nWaiting {delay:.1f}s before next video...")
                await asyncio.sleep(delay)

    # Print summary
    print(f"\n{'='*50}")
    print(f"=== Batch Complete ===")
    print(f"{'='*50}")

    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    print(f"Successful: {len(successful)}/{len(urls)}")

    for r in successful:
        print(f"  ✓ {r['url'][:50]}... -> {r['dir']}")

    if failed:
        print(f"\nFailed: {len(failed)}")
        for r in failed:
            print(f"  ✗ {r['url'][:50]}...")
            print(f"    Error: {r.get('error', 'Unknown')[:100]}")

    return results


async def extract_batch_parallel_async(
    urls: list[str],
    output_base: Path = None,
    whisper_model: str = "base",
    max_concurrent: int = 4,
    local: bool = False,
) -> list[dict]:
    """
    Extract content from multiple TikTok videos in parallel.

    Uses multiple browser tabs to download videos simultaneously.
    Processing (frames, OCR, transcription) is done sequentially after downloads.

    Args:
        local: If True, auto-detect browser (for local dev). If False, use Docker paths.
    """
    if output_base is None:
        output_base = Path(__file__).parent / "output"

    output_base.mkdir(parents=True, exist_ok=True)

    print(f"=== TikTok Parallel Extractor (zendriver) ===")
    print(f"Processing {len(urls)} videos with {max_concurrent} parallel tabs")
    print(f"Output: {output_base}")
    print()

    # Step 1: Download all videos in parallel
    print("Phase 1: Downloading videos in parallel...")
    download_results = await download_batch_parallel(
        urls,
        output_base,
        max_concurrent=max_concurrent,
        local=local,
    )

    # Step 2: Process downloaded videos sequentially
    print("\nPhase 2: Processing downloaded videos...")
    results = []

    for i, dl_result in enumerate(download_results):
        url = dl_result.get("url", urls[i] if i < len(urls) else "unknown")

        if not dl_result.get("success"):
            print(f"\n[{i+1}/{len(urls)}] Skipping (download failed)")
            results.append({"success": False, "url": url, "error": "Download failed"})
            continue

        video_path = dl_result.get("video_path")
        if not video_path or not Path(video_path).exists():
            print(f"\n[{i+1}/{len(urls)}] Skipping (no video file)")
            results.append({"success": False, "url": url, "error": "No video file"})
            continue

        print(f"\n[{i+1}/{len(urls)}] Processing: {url[:50]}...")

        # Create work directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        work_dir = output_base / f"{timestamp}_{url_hash}"
        work_dir.mkdir(parents=True, exist_ok=True)

        # Move video to work dir
        import shutil
        new_video_path = work_dir / "video.webm"
        shutil.move(str(video_path), str(new_video_path))

        try:
            result = process_video(new_video_path, work_dir, whisper_model, dl_result.get("metadata", {}))
            result["success"] = True
            result["url"] = url
            results.append(result)
        except Exception as e:
            print(f"  Error processing: {e}")
            results.append({"success": False, "url": url, "error": str(e)})

    # Print summary
    print(f"\n{'='*50}")
    print(f"=== Batch Complete ===")
    print(f"{'='*50}")

    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    print(f"Successful: {len(successful)}/{len(urls)}")
    for r in successful:
        print(f"  ✓ {r['url'][:50]}...")

    if failed:
        print(f"\nFailed: {len(failed)}")
        for r in failed:
            print(f"  ✗ {r.get('url', 'unknown')[:50]}...")

    return results


async def login_interactive():
    """Interactive login to TikTok."""
    print("=== TikTok Login ===")
    print("A browser window will open.")
    print("Log into TikTok, then press Enter in this terminal.")
    print()

    async with TikTokDownloader() as downloader:
        await downloader.login_interactive()

    print("\nLogin session saved! You can now run extractions.")


def main():
    parser = argparse.ArgumentParser(description="Extract content from TikTok videos")
    parser.add_argument("urls", nargs="?", help="TikTok video URL(s) - comma-separated for multiple")
    parser.add_argument("--login", action="store_true", help="Login to TikTok interactively")
    parser.add_argument("--model", default="base", choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper model size (default: base)")
    parser.add_argument("--output", "-o", type=Path, default=None,
                        help="Output directory (default: ./output)")
    parser.add_argument("--delay", "-d", type=float, default=3.0,
                        help="Delay between videos in seconds (default: 3.0)")
    parser.add_argument("--parallel", "-p", type=int, default=0, metavar="N",
                        help="Download N videos in parallel using multiple tabs (default: sequential)")
    parser.add_argument("--local", "-l", action="store_true",
                        help="Run locally (auto-detect browser instead of Docker paths)")

    args = parser.parse_args()

    # Handle login
    if args.login:
        asyncio.run(login_interactive())
        return

    # Require URLs if not logging in
    if not args.urls:
        parser.print_help()
        print("\nError: Please provide URLs or use --login")
        sys.exit(1)

    # Parse comma-separated URLs
    urls = [u.strip() for u in args.urls.split(",") if u.strip()]

    if not urls:
        print("Error: No valid URLs provided")
        sys.exit(1)

    # Run extraction
    try:
        if args.parallel > 0:
            # Parallel mode: download multiple videos simultaneously
            results = asyncio.run(extract_batch_parallel_async(
                urls,
                args.output,
                args.model,
                max_concurrent=args.parallel,
                local=args.local,
            ))
        else:
            # Sequential mode: one video at a time
            results = asyncio.run(extract_batch_async(
                urls,
                args.output,
                args.model,
                args.delay,
                local=args.local,
            ))

        failed = [r for r in results if not r.get("success")]
        if failed:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
