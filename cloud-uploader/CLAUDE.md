# Cloud Uploader Pipeline

Automated pipeline for TikTok video research: search → download → process → upload to cloud.

## Quick Start

### Local (Mac)
```bash
cd /Users/rhu/projects/tiktok_scrapper

# Process queries locally (uses --dev for browser)
python3 cloud-uploader/pipeline.py --local --start 0 --count 10

# Single query test
python3 cloud-uploader/pipeline.py --local --query "tokyo ramen spots" --max-results 5

# Process all queries
python3 cloud-uploader/pipeline.py --local --start 0
```

### Droplet (Production)
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

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PIPELINE ORCHESTRATOR                     │
│                      (pipeline.py)                           │
├─────────────────────────────────────────────────────────────┤
│  • Reads queries from research_list.csv                      │
│  • Manages retry logic at each step                          │
│  • Tracks progress for resume capability                     │
│  • Handles graceful shutdown (Ctrl+C)                        │
│  • Monitors disk space                                       │
│  • Cleans up Chrome processes periodically                   │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   SEARCH     │    │   DOWNLOAD   │    │   PROCESS    │
│ (Serper API) │───▶│ (zendriver)  │───▶│  (Whisper +  │
│              │    │              │    │   Claude)    │
└──────────────┘    └──────────────┘    └──────────────┘
                                               │
                    ┌──────────────────────────┘
                    ▼
        ┌──────────────────────┐
        │       UPLOAD         │
        │  (GCS + Supabase)    │
        │                      │
        │  Only delete mp4     │
        │  after DB confirms   │
        └──────────────────────┘
```

## Anti-Detection Strategy

The pipeline implements several measures to avoid TikTok rate limiting:

| Measure | Implementation |
|---------|----------------|
| Random delays | 2-5s before download, 5-10s between queries |
| Browser rotation | Uses 3 workers with separate profiles |
| Profile cleanup | Clears cache/cookies every 3 queries |
| Chrome cleanup | Kills zombie processes periodically |
| Variable workers | Can adjust worker count per run |
| Duplicate skip | Checks database before downloading |

## Retry & Failure Logic

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

## Production Safety Features

### Graceful Shutdown
Press Ctrl+C to stop gracefully. The pipeline will:
1. Finish the current query
2. Save progress to progress.json
3. Exit cleanly

### Disk Space Monitoring
Pipeline checks disk space before each query and stops if < 1GB available.

### Video Deletion Safety
Videos (mp4) are ONLY deleted after:
1. Successfully uploaded to GCS
2. Successfully inserted into Supabase
3. Confirmed by checking `db.video_exists(video_id)`

### Duplicate Detection
Before downloading, the pipeline checks the database for existing videos:
- Extracts video IDs from search result URLs
- Queries `db.get_all_video_ids()` to get existing IDs
- Skips downloading videos already in the database
- Logs: "Skipped N videos already in database"

## Dependencies

### Local (Mac)
```bash
# Install ffmpeg
brew install ffmpeg

# Python packages
pip3 install httpx python-dotenv aiohttp aiofiles zendriver \
    opencv-python-headless google-cloud-storage supabase

# PyTorch + Whisper
pip3 install torch openai-whisper
```

### Droplet (Linux)
```bash
apt-get install -y ffmpeg xvfb chromium-browser

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
│  - Supabase DB   │  → Insert record with metadata + query
│  - Cleanup mp4   │  → Only after confirmed in DB
└──────────────────┘
```

## Files

### pipeline.py
Main orchestrator that runs the full pipeline for each query.

```bash
# Options
--start N        # Start from query index N (default: 0)
--count N        # Process N queries (omit to process all)
--query "..."    # Process single query instead of CSV
--max-results N  # Max videos per query (default: 20)
--workers N      # Browser workers for download (default: 3)
--whisper-model  # tiny|base|small|medium|large (default: base)
--dry-run        # Search only, don't download
--resume         # Skip already processed queries
--local          # Use dev settings for local Mac development
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
--query "..."    # Query string to store with videos
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
        ├── video.mp4              # Downloaded video (deleted after upload)
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
CREATE TABLE videos (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id        TEXT UNIQUE NOT NULL,
  url             TEXT,
  author          TEXT,
  title           TEXT,
  transcript      TEXT,
  ocr_text        TEXT,
  gcs_prefix      TEXT,
  frame_count     INTEGER,
  query           TEXT,                    -- NEW: search query that found this video
  processed_at    TIMESTAMP WITH TIME ZONE,
  uploaded_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for searching
CREATE INDEX idx_videos_query ON videos(query);
CREATE INDEX idx_videos_author ON videos(author);
```

**IMPORTANT**: Add the `query` column if it doesn't exist:
```sql
ALTER TABLE videos ADD COLUMN IF NOT EXISTS query TEXT;
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
pkill -9 chrome
```

### Disk full
```bash
pip3 cache purge
rm -rf /root/.cache/pip/*
apt-get clean
# Pipeline will auto-stop when disk < 1GB
```

### Rate limited by Serper
The search automatically handles rate limits. If persistent, add delays between queries.

### OCR failing
Check ANTHROPIC_API_KEY is set and has credits.

### Upload failures
Check GCS credentials and Supabase connection:
```bash
python3 -c "import db; print(db.get_stats())"
```

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

## Monitoring

Watch logs in real-time:
```bash
tail -f cloud-uploader/logs/latest.log
```

Check progress:
```bash
cat cloud-uploader/progress.json
cat cloud-uploader/failures.json
```

Check database:
```bash
python3 -c "import db; print(db.get_stats())"
```
