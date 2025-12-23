# TikTok Scrapper

A Python tool to extract content from TikTok videos for analysis.
Uses zendriver (undetectable Chrome automation) for downloads.

## What it does

Given a TikTok URL, extracts:
- **Video** - downloads using undetectable browser automation via `video.captureStream()`
- **Frames** - extracts key frames as images using ffmpeg
- **Audio transcript** - speech-to-text via Whisper (local, free)
- **On-screen text** - text overlays, captions, locations via Claude vision API
- **Metadata** - video info from TikTok (title, author, etc.)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Docker Container                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   Xvfb      │  │  Fluxbox    │  │   x11vnc    │              │
│  │ (Display)   │  │  (Window    │  │   (VNC      │              │
│  │   :99       │  │   Manager)  │  │   :5900)    │              │
│  └──────┬──────┘  └─────────────┘  └─────────────┘              │
│         │                                                        │
│  ┌──────▼──────────────────────────────────────────────────┐    │
│  │                    Chromium Browser                      │    │
│  │  (--no-sandbox --disable-web-security)                  │    │
│  │                                                          │    │
│  │  ┌────────────────────────────────────────────────────┐ │    │
│  │  │  video.captureStream() → MediaRecorder → WebM      │ │    │
│  │  └────────────────────────────────────────────────────┘ │    │
│  └──────────────────────────────────────────────────────────┘    │
│                              │                                   │
│  ┌───────────────────────────▼───────────────────────────────┐  │
│  │                    Python (zendriver)                      │  │
│  │  tiktok.py → extract.py → ffmpeg → whisper → claude API  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## File Structure

```
tiktok_scrapper/
├── claude.md              # This documentation
├── extract.py             # Main extraction pipeline (frames, OCR, transcription)
├── tiktok.py              # TikTok video downloader using zendriver
├── requirements.txt       # Python dependencies
├── Dockerfile             # Docker image definition
├── docker-compose.yml     # Docker services configuration
├── docker-entrypoint.sh   # Container startup script
├── .dockerignore          # Files excluded from Docker build
├── browser_profile/       # Persistent browser session (login cookies)
├── downloads/             # Temporary download directory
└── output/                # Extracted content organized by timestamp
```

## Key Code Locations

### tiktok.py - Video Downloader

| Function | Lines | Description |
|----------|-------|-------------|
| `TikTokDownloader.__init__` | 34-52 | Initialize with profile dir, headless mode, and local flag |
| `TikTokDownloader.start` | 61-90 | Start browser with local/Docker-compatible config |
| `download_video_via_canvas` | 120-360 | Main capture method using `video.captureStream()` |
| `download_batch_parallel` | 651-950 | Parallel downloads using multiple browser tabs |

**Critical browser configuration** (`tiktok.py:65-86`):
```python
# Build browser args
browser_args = [
    "--disable-web-security",  # Required for video.captureStream() on CDN videos
    "--autoplay-policy=no-user-gesture-required",
]

if not self.local:
    # Docker-specific args
    browser_args.extend([
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-software-rasterizer",
    ])

config = Config(
    headless=self.headless,
    user_data_dir=str(self.profile_dir),
    sandbox=self.local,  # True for local, False for Docker/root
    browser_executable_path=None if self.local else "/usr/bin/chromium",
    browser_connection_timeout=2.0,  # Increased for Docker startup time
    browser_args=browser_args,
)
```

**Video capture JavaScript** (`tiktok.py:195-281`):
- Uses `video.captureStream()` directly on the video element
- Records with MediaRecorder to WebM format
- Converts blob to base64 for retrieval via `page.evaluate()`

**Parallel mode video ready check** (`tiktok.py:733-743`):
- Waits for `video.readyState >= 3` before starting capture
- JavaScript-side `waitForReady()` promise with 30s timeout
- Pause → seek to 0 → wait 500ms → play sequence for reliable capture

### extract.py - Extraction Pipeline

| Function | Lines | Description |
|----------|-------|-------------|
| `get_video_duration` | 45-87 | Get duration with fallbacks for WebM |
| `extract_frames` | 90-114 | Extract frames using ffmpeg |
| `ocr_frames` | 134-234 | OCR using Claude vision API (batched) |
| `transcribe_audio` | 237-251 | Transcribe using Whisper |
| `extract_batch_async` | 368-440 | Sequential extraction with shared browser |
| `extract_batch_parallel_async` | 443-540 | Parallel download, sequential processing |

### docker-entrypoint.sh - Container Startup

```bash
#!/bin/bash
set -e

# Start dbus (required for Chromium)
mkdir -p /run/dbus
dbus-daemon --system --fork 2>/dev/null || true

# Start Xvfb (virtual display)
Xvfb :99 -screen 0 1920x1080x24 &
sleep 2

# Start window manager
fluxbox 2>/dev/null &
sleep 1

# Optional VNC for debugging
if [ "${VNC_ENABLED:-false}" = "true" ]; then
    x11vnc -display :99 -forever -nopw -quiet 2>/dev/null &
fi

# Clear stale browser singleton files (from previous container runs)
rm -f /app/browser_profile/Singleton* 2>/dev/null || true

exec "$@"
```

## Critical Technical Decisions & Fixes

### 1. Why video.captureStream() instead of direct download?

TikTok's CDN returns **403 Forbidden** for direct video URL requests even with proper cookies/headers. The video is only accessible within the browser context.

**Failed approaches:**
- Direct download via aiohttp: 403 Forbidden
- Browser fetch() API: 403 Forbidden
- Canvas capture with drawImage(): SecurityError (tainted canvas from cross-origin video)

**Working approach:**
- `video.captureStream()` directly on the video element with `--disable-web-security` browser flag
- Records playback in real-time using MediaRecorder
- Outputs WebM format (VP9 codec)

### 2. Browser Connection Timeout

**Problem:** zendriver's default `browser_connection_timeout` is 0.25 seconds, but Chromium in Docker takes 6-7 seconds to start and open the debugging port.

**Fix:** Set `browser_connection_timeout=2.0` in the Config (`tiktok.py:67`)

### 3. Stale Browser Profile Singleton Files

**Problem:** When a Docker container exits, the browser profile retains `Singleton*` files pointing to the old container's temp paths. New containers can't connect because those paths don't exist.

**Fix:** Clear singleton files on container startup (`docker-entrypoint.sh:29`):
```bash
rm -f /app/browser_profile/Singleton* 2>/dev/null || true
```

### 4. Cross-Origin Video Capture

**Problem:** `canvas.captureStream()` fails with "Canvas is not origin-clean" because the video source is from TikTok's CDN (different origin).

**Fix:** Add `--disable-web-security` to browser args, then use `video.captureStream()` directly instead of canvas-based capture.

### 5. Base64 Data Transfer

**Problem:** Browser download mechanism (`a.click()` with blob URL) doesn't work reliably in headless mode - files are 0 bytes.

**Fix:** Convert captured video blob to base64 in JavaScript, retrieve via `page.evaluate()`, decode in Python:
```javascript
// In browser (tiktok.py:227-240)
const buffer = await blob.arrayBuffer();
const bytes = new Uint8Array(buffer);
let binary = '';
for (let i = 0; i < bytes.length; i += 32768) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + 32768));
}
window.__captureData = btoa(binary);
```

```python
# In Python (tiktok.py:328-341)
video_data = await self.page.evaluate("window.__captureData")
video_bytes = base64.b64decode(video_data)
```

### 6. Local vs Docker Mode

**Problem:** Browser executable path `/usr/bin/chromium` is hardcoded for Docker, but doesn't exist on local Mac/Linux machines.

**Fix:** Added `--local` / `-l` flag that:
- Sets `browser_executable_path=None` to auto-detect Chrome/Chromium
- Sets `sandbox=True` (safer for non-root local execution)
- Skips Docker-specific flags (`--disable-gpu`, `--disable-dev-shm-usage`)

```python
# tiktok.py:79-84
config = Config(
    sandbox=self.local,  # True for local, False for Docker/root
    browser_executable_path=None if self.local else "/usr/bin/chromium",
    ...
)
```

### 7. Parallel Mode Video Ready Race Condition

**Problem:** In parallel mode with multiple tabs, videos fail with "Play failed: Failed to load because no supported source was found" because `video.play()` is called before the video is fully loaded.

**Fix:** Added multi-layer waiting before capture (`tiktok.py:733-893`):

1. **Python-side wait:** Poll until `video.readyState >= 3` (HAVE_FUTURE_DATA)
2. **JavaScript-side wait:** `waitForReady()` promise that polls/listens for `canplay` event
3. **Seek delay:** Pause video → set `currentTime = 0` → wait 500ms → then play

```javascript
// Wait sequence in capture JavaScript
video.muted = true;
video.pause();
video.currentTime = 0;
setTimeout(() => {
    video.play().then(() => { recorder.start(500); ... });
}, 500);
```

### 8. None-Safe Video Info Extraction

**Problem:** In parallel mode, `video_info.get('duration', 60)` returns `None` if the key exists with a `None` value, causing format string errors.

**Fix:** Use `or` instead of default parameter (`tiktok.py:751-754`):
```python
# Before (broken):
duration = video_info.get('duration', 60)  # Returns None if key exists with None value

# After (fixed):
duration = video_info.get('duration') or 60  # Falls back to 60 if None
width = video_info.get('videoWidth') or 720
height = video_info.get('videoHeight') or 1280
```

## Docker Deployment

### Quick Start

```bash
# Build the image
docker compose build

# Run extraction
docker compose run --rm scraper python extract.py "https://tiktok.com/@user/video/123"

# Run with parallel downloads (4 tabs)
docker compose run --rm scraper python extract.py -p 4 "url1,url2,url3,url4"

# Interactive shell
docker compose run --rm scraper bash
```

### VNC Debugging

Connect to `localhost:5900` with any VNC viewer to see the browser in action.

```bash
# Enable VNC (already enabled in docker-compose.yml)
VNC_ENABLED=true docker compose run --rm scraper python extract.py "url"
```

### docker-compose.yml Services

```yaml
services:
  scraper:
    build: .
    environment:
      - DISPLAY=:99
      - VNC_ENABLED=true
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      - ./tiktok.py:/app/tiktok.py      # Live code updates
      - ./extract.py:/app/extract.py
      - ./output:/app/output
      - ./browser_profile:/app/browser_profile
      - ./downloads:/app/downloads
    ports:
      - "5900:5900"  # VNC
    shm_size: '2gb'  # Required for Chrome
```

### DigitalOcean Droplet Setup

```bash
# SSH to droplet
ssh tiktok@64.225.6.32

# Install Docker
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2
sudo usermod -aG docker tiktok

# Clone/copy files
cd /home/tiktok/tiktok_scrapper

# Set API key
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# Build and run
docker compose build
docker compose run --rm scraper python extract.py "url"
```

## Usage Examples

### Command Line

```bash
# Single video (Docker)
python extract.py "https://tiktok.com/@user/video/123"

# Single video (local Mac/Linux - auto-detects browser)
python extract.py --local "https://tiktok.com/@user/video/123"

# Multiple videos (comma-separated)
python extract.py "url1,url2,url3"

# Parallel mode (4 simultaneous downloads)
python extract.py --parallel 4 "url1,url2,url3,url4"

# Parallel mode on local machine
python extract.py -l -p 4 "url1,url2,url3,url4"

# Custom Whisper model (tiny/base/small/medium/large)
python extract.py --model small "url"

# Custom output directory
python extract.py -o ./my_output "url"

# Login to TikTok (saves session for future use)
python extract.py --login
```

### Command Line Flags

| Flag | Short | Description |
|------|-------|-------------|
| `--local` | `-l` | Run locally (auto-detect browser instead of Docker's `/usr/bin/chromium`) |
| `--parallel N` | `-p N` | Download N videos simultaneously using multiple browser tabs |
| `--model NAME` | | Whisper model: tiny, base, small, medium, large |
| `--output DIR` | `-o` | Custom output directory |
| `--delay SECS` | `-d` | Delay between sequential downloads (default: 3.0) |
| `--login` | | Interactive TikTok login (saves session to browser_profile/) |

### Programmatic Usage

```python
import asyncio
from pathlib import Path
from tiktok import TikTokDownloader, download_batch_parallel
from extract import extract_batch_async, extract_batch_parallel_async

# Download single video
async def download_one():
    async with TikTokDownloader() as tt:
        result = await tt.download_video(url, Path("video.webm"))
        print(f"Downloaded: {result['video_path']}")

# Download multiple in parallel
async def download_many():
    results = await download_batch_parallel(
        urls=["url1", "url2", "url3", "url4"],
        output_dir=Path("./output"),
        max_concurrent=4,
    )

# Full extraction pipeline
async def extract_all():
    results = await extract_batch_parallel_async(
        urls=["url1", "url2", "url3", "url4"],
        whisper_model="base",
        max_concurrent=4,
    )

asyncio.run(extract_all())
```

## Output Structure

```
output/
└── 20251222_205856_17668d73/
    ├── video.webm         # Captured video (VP9 codec, ~70MB for 2min video)
    ├── audio.mp3          # Extracted audio
    ├── transcript.txt     # Speech transcription (Whisper)
    ├── ocr.json           # On-screen text per frame (Claude vision)
    ├── ocr_summary.txt    # Deduplicated on-screen text
    ├── metadata.json      # TikTok video metadata
    └── frames/            # Extracted video frames
        ├── frame_001.jpg
        ├── frame_002.jpg
        └── ...
```

## Troubleshooting

### "Failed to connect to browser... pass no_sandbox=True"

**Cause:** Browser startup is slow in Docker, or stale singleton files exist.

**Fix:**
1. Ensure `sandbox=False` in Config
2. Ensure `browser_connection_timeout=2.0` or higher
3. Clear browser profile: `rm -rf browser_profile/*`

### "Canvas is not origin-clean" / SecurityError

**Cause:** Trying to use canvas-based capture on cross-origin video.

**Fix:** Use `video.captureStream()` directly with `--disable-web-security` browser flag.

### Video file is 0 bytes

**Cause:** Browser download mechanism doesn't work in headless mode.

**Fix:** Use base64 transfer method (retrieve blob data via JavaScript, decode in Python).

### "No space left on device" during Docker build

**Fix:**
```bash
docker system prune -a -f --volumes
```

### Browser profile permission errors

**Cause:** Profile created by root in Docker, but host user can't access.

**Fix:**
```bash
sudo rm -rf browser_profile/*
```

## Dependencies

### System (installed in Docker)
- chromium
- ffmpeg
- xvfb, x11vnc, fluxbox (display)
- dbus, dbus-x11 (required by Chromium)

### Python (requirements.txt)
- zendriver - Undetectable Chrome automation
- anthropic - Claude API for OCR
- openai-whisper - Audio transcription
- Pillow - Image processing
- aiohttp, aiofiles - Async HTTP/file operations

### Environment Variables
```bash
ANTHROPIC_API_KEY=sk-ant-...  # Required for OCR
```

## How Detection Avoidance Works

This tool uses **zendriver** which:
- Controls Chrome via Chrome DevTools Protocol (CDP), not WebDriver
- Leaves no detectable automation fingerprints (`navigator.webdriver` is undefined)
- Maintains real browser profiles with cookies/history
- Looks identical to a human user browsing

The browser session is saved to `browser_profile/`, so login persists across runs.

## Performance Notes

- Video capture takes approximately 1x playback time (2 min video = 2 min capture)
- Frame extraction: ~5 seconds for 200 frames
- OCR: ~2-3 seconds per batch of 5 frames (46 batches for 228 frames ≈ 2-3 minutes)
- Whisper transcription: ~30 seconds for 2 min audio (base model)

Total time for a 2-minute video: ~5-6 minutes

## Future Improvements

- [ ] Support for TikTok slideshows (image carousels)
- [ ] Retry logic for failed captures
- [ ] Progress callbacks for long-running operations
- [ ] Support for private/friends-only videos (requires login)
- [ ] Caching of already-processed videos
