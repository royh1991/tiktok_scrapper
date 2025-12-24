# TikTok Video Scrapper

Fast, parallel TikTok video downloader and processor for research purposes.

## Architecture

Downloads TikTok videos at **network speed** (not playback speed) by:
1. Using zendriver to load TikTok pages (undetectable from datacenter IPs)
2. Intercepting video CDN URLs via Chrome DevTools Protocol (CDP)
3. Downloading original MP4 files directly via HTTP with captured cookies
4. Extracting metadata (creator, caption) from embedded page JSON

## Project Structure

```
tiktok_scrapper/
├── tiktok_downloader.py  # Main downloader (CDN intercept + parallel HTTP)
├── process.py            # OCR (Claude Haiku) + Whisper transcription
├── upload.py             # Upload to GCS + insert to Supabase
├── db.py                 # Supabase client helpers
├── setup.sh              # Droplet setup script
├── requirements.txt      # Python dependencies
├── .env                  # Credentials (not in git)
├── output/               # Downloaded videos (video_id/video.mp4 + metadata.json)
└── browser_profiles/     # Persistent browser sessions
```

## Usage

### Download videos
```bash
# Dev mode (Mac)
python tiktok_downloader.py --dev download --file urls.txt

# Production (droplet)
python tiktok_downloader.py download --file urls.txt

# Specific URLs
python tiktok_downloader.py --dev download URL1 URL2 URL3

# Search and download
python tiktok_downloader.py --dev search "tokyo food" --limit 20
```

### Process videos (OCR + transcription)
```bash
python process.py                    # Process all unprocessed in output/
python process.py output/7353240*/   # Process specific directories
python process.py --watch            # Watch mode for new downloads
```

### Upload to cloud
```bash
python upload.py                     # Upload all unuploaded
python upload.py output/7353240*/    # Upload specific directories
```

## Output Structure

Each video gets its own folder named by video ID:
```
output/
└── 7353240544740429087/
    ├── video.mp4           # Original from TikTok CDN
    ├── metadata.json       # {video_id, video_url, creator, caption, ...}
    ├── audio.mp3           # Extracted audio
    ├── transcript.txt      # Whisper transcription
    ├── ocr.json            # Per-frame OCR results
    └── frames/             # Extracted video frames
```

## Droplet Setup

```bash
# On a fresh Ubuntu 22.04 droplet:
sudo bash setup.sh

# Then as tiktok user:
sudo su - tiktok
source ~/tiktok_scrapper/venv/bin/activate
export DISPLAY=:99
python tiktok_downloader.py download --file urls.txt
```

## Performance

- **Download**: ~5-7s per video for URL extraction, parallel HTTP downloads
- **891 videos**: ~30-45 minutes (vs 5-15 hours with old playback capture)
- **Workers**: Default 5 browser workers, 10 parallel downloads

## Environment Variables (.env)

```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_APPLICATION_CREDENTIALS=/path/to/gcs-key.json
GCS_BUCKET=your-bucket
```
