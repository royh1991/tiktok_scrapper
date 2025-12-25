# TikTok Search

Extract relevant TikTok video URLs using Google search (works from datacenter IPs).

## Quick Start

```bash
cd /home/tiktok/search_experiments
source venv/bin/activate
DISPLAY=:99 python tiktok_search.py "tokyo travel itinerary"
```

## How It Works

**Problem**: TikTok blocks direct search from datacenter IPs.

**Solution**: Use Google search with multiple query formats:
1. `tiktok.com {query}` - Broad results
2. `site:tiktok.com "{query}"` - Exact phrase match
3. `site:tiktok.com {query}` - Site-restricted

Results are combined and deduplicated for maximum coverage.

## Usage

```bash
# Search (auto mode - Google with hashtag fallback)
python tiktok_search.py "tokyo travel itinerary"

# Force Google only
python tiktok_search.py --method google "tokyo travel"

# Force hashtags only  
python tiktok_search.py --method hashtags "tokyo travel"

# Use specific hashtags
python tiktok_search.py --hashtags "tokyotravel,japantravel"

# Limit results
python tiktok_search.py "tokyo travel" --max 30

# Save to JSON
python tiktok_search.py "tokyo travel" -o results.json

# Local/dev mode (Mac)
python tiktok_search.py --dev "tokyo travel"
```

## Performance

| Method | Results | Relevance | Speed |
|--------|---------|-----------|-------|
| Google | 30-50 | Excellent | ~15s |
| Hashtags | 30-60 | Good | ~20s |
| Auto | 30-60 | Best | ~20s |

## Output

```json
{
  "query": "tokyo travel itinerary",
  "method": "google",
  "count": 34,
  "urls": [
    "https://www.tiktok.com/@user/video/1234567890",
    ...
  ]
}
```

## Files

```
/home/tiktok/search_experiments/
├── tiktok_search.py       # Main search script
├── venv/                  # Python environment
├── browser_profiles/      # Browser sessions
├── CLAUDE.md              # This file
└── *.json                 # Search results
```

## Combining with Downloader

```bash
# Search and save
python tiktok_search.py "tokyo travel" -o results.json

# Extract URLs
cat results.json | jq -r '.urls[]' > urls.txt

# Download videos
cd /home/tiktok/download_experiments
python tiktok_downloader.py download --file urls.txt
```

## Why Google Search?

1. **Works from datacenter** - Google doesn't block like TikTok does
2. **Better relevance** - Google's ranking finds truly relevant videos
3. **Broader coverage** - Multiple query formats combined
4. **No login required** - Unlike TikTok direct search

## Troubleshooting

### Google captcha
If you see "unusual traffic", the script automatically skips that query format and tries others.

### Few results
Try a more specific query, or use `--method hashtags` for broader but less relevant results.

### Browser connection failed
Clear browser profiles: `rm -rf browser_profiles/*`
