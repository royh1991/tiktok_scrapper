# Cloud Uploader Pipeline

Automated pipeline for TikTok video research: search → download → process → upload to cloud.

## Quick Start

```bash
cd /home/tiktok/tiktok_scrapper_repo
export DISPLAY=:99

# Process queries from research_list.csv
python3 cloud-uploader/pipeline.py --start 0 --count 10

# Resume from where you left off
python3 cloud-uploader/pipeline.py --resume --count 50

# Single query test
python3 cloud-uploader/pipeline.py --query "tokyo ramen spots" --max-results 5
```

## Retry & Failure Logic

The pipeline has comprehensive retry logic at every step:

| Step | Max Retries | Backoff | Behavior |
|------|-------------|---------|----------|
| Search | 3 | Exponential (2s, 4s, 8s) | Retries Serper API calls |
| Download | 2 | Exponential | Retries failed URLs individually |
| Process | 3 | Exponential | Per-video retry with --reprocess |
| Upload | 3 | Exponential | Retries GCS + database |

### Failure Tracking

All failures are logged to `cloud-uploader/failures.json`:
```json
{
  "timestamp": "2024-01-15T10:30:00",
  "type": "download",
  "query_index": 5,
  "query": "tokyo ramen spots",
  "error": "3 URLs failed to download",
  "details": {"failed_urls": ["https://..."]}
}
```

### Status Types

| Status | Meaning |
|--------|---------|
| `success` | All videos uploaded |
| `partial_success` | Some videos uploaded, some failed |
| `search_failed` | No results after 3 retries |
| `download_failed` | No videos downloaded after retries |
| `processing_failed` | No videos passed validation |
| `upload_failed` | Upload failed after 3 retries |
| `error` | Unexpected exception |

## Dependencies

### System Packages
```bash
apt-get install -y ffmpeg xvfb chromium-browser
```

### Python Packages
```bash
pip3 install --break-system-packages \
    httpx \
    python-dotenv \
    aiohttp \
    aiofiles \
    zendriver \
    opencv-python-headless \
    google-cloud-storage \
    supabase

# PyTorch CPU-only (for Whisper)
pip3 install --break-system-packages torch --index-url https://download.pytorch.org/whl/cpu
pip3 install --break-system-packages openai-whisper
```

### Environment Variables (.env)
```bash
# Required in /home/tiktok/tiktok_scrapper_repo/.env
ANTHROPIC_API_KEY=sk-ant-...          # For OCR with Claude Haiku
SERPER_API_KEY=...                     # For Google video search (serper.dev)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/gcs-key.json
GCS_BUCKET=tiktokscrapper-videos
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...
```

## Pipeline Overview

```
research_list.csv
       ↓
┌──────────────────┐
│  1. SEARCH       │  tiktok_search.py (Serper API)
│  Find TikTok     │  → Returns list of video URLs
│  video URLs      │
└────────┬─────────┘
         ↓
┌──────────────────┐
│  2. DOWNLOAD     │  tiktok_downloader.py (zendriver + CDP)
│  Download videos │  → output/{query}/video.mp4 + metadata.json
│  + metadata      │
└────────┬─────────┘
         ↓
┌──────────────────┐
│  3. PROCESS      │  process.py (OpenCV + Whisper + Claude)
│  - Extract frames│  → frames/, audio.mp3, transcript.txt, ocr.json
│  - OCR text      │
│  - Transcribe    │
└────────┬─────────┘
         ↓
┌──────────────────┐
│  4. VALIDATE     │  upload.py
│  Check all files │  → Ensure transcript, OCR, audio exist
│  exist & valid   │
└────────┬─────────┘
         ↓
┌──────────────────┐
│  5. UPLOAD       │  upload.py
│  - GCS bucket    │  → gs://bucket/videos/{video_id}/
│  - Supabase DB   │  → Insert record with metadata
│  - Cleanup local │
└──────────────────┘
```

## Files

### pipeline.py
Main orchestrator that runs the full pipeline for each query.

```bash
# Options
--start N        # Start from query index N (default: 0)
--count N        # Process N queries
--query "..."    # Process single query instead of CSV
--max-results N  # Max videos per query (default: 20)
--workers N      # Browser workers for download (default: 3)
--whisper-model  # tiny|base|small|medium|large (default: base)
--dry-run        # Search only, don't download
--resume         # Skip already processed queries
```

### upload.py
Uploads processed videos to GCS and Supabase.

```bash
# Options
--output-dir     # Directory to scan (default: ../output)
--max-frames N   # Max frames to upload (default: 20)
--include-video  # Also upload video.mp4 to GCS
--dry-run        # Preview without uploading
--keep           # Keep local files after upload
```

### progress.json
Tracks processed queries for resume capability.

```json
{
  "processed_queries": ["0:Tokyo weekend itinerary 2024", ...],
  "stats": {"total": 10, "success": 8, "failed": 2}
}
```

## Output Structure

```
output/
└── query_00000_Tokyo_weekend_itinerary_2024/
    └── 7319467787859053825/
        ├── video.mp4              # Downloaded video
        ├── metadata.json          # {video_id, creator, caption, ...}
        ├── audio.mp3              # Extracted audio
        ├── transcript.txt         # Whisper transcription
        ├── transcript_timestamps.json
        ├── ocr.json               # {items: [...], scenes: N}
        └── frames/                # Scene frames (001_t0.0s.jpg, ...)
```

## GCS Structure

```
gs://tiktokscrapper-videos/
└── videos/
    └── 7319467787859053825/
        ├── metadata.json
        ├── transcript.txt
        ├── transcript_timestamps.json
        ├── ocr.json
        ├── audio.mp3
        └── frames/
            ├── 001_t0.0s.jpg
            ├── 019_t11.0s.jpg
            └── ... (max 20 frames)
```

## Database Schema (Supabase)

Table: `videos`
```sql
video_id        TEXT PRIMARY KEY
url             TEXT
author          TEXT
title           TEXT
transcript      TEXT
ocr_text        TEXT
gcs_prefix      TEXT
frame_count     INTEGER
processed_at    TIMESTAMP
```

## Validation Rules

Before uploading, each video must have:
- `transcript.txt` with content (min 3 chars)
- `ocr.json` valid JSON with items array
- `audio.mp3` exists
- `metadata.json` exists

If validation fails, the video is reprocessed once before skipping.

## Troubleshooting

### Xvfb not running
```bash
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99
```

### Browser crashes
```bash
rm -rf /home/tiktok/tiktok_scrapper_repo/browser_profiles/*
```

### Disk full
```bash
pip3 cache purge
rm -rf /root/.cache/pip/*
apt-get clean
```

### Rate limited by Serper
The search automatically handles rate limits. If persistent, add delays between queries.

### OCR failing
Check ANTHROPIC_API_KEY is set and has credits.

## Performance

| Step | Time per video |
|------|----------------|
| Search | ~0.5s per query |
| Download | ~5-10s |
| Process | ~30-60s (depends on video length) |
| Upload | ~5-10s |

For 20 videos per query: ~15-20 minutes per query.

## Resume After Failure

The pipeline saves progress after each query. To resume:
```bash
python3 cloud-uploader/pipeline.py --resume --count 100
```

Already processed queries (in progress.json) will be skipped.
