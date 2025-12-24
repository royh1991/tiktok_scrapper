# TikTok Search

Extract video URLs from TikTok using zendriver (undetectable Chrome automation).

## Quick Start

```bash
cd /home/tiktok/search_experiments
source venv/bin/activate
DISPLAY=:99 python tiktok_search.py "tokyo travel"
```

## How It Works

**Problem**: TikTok blocks direct search from datacenter IPs (returns "Page not available").

**Solution**: Use hashtag pages (`/tag/{hashtag}`) which are not blocked:
1. Convert search query to relevant hashtags
2. Fetch videos from each hashtag page
3. Deduplicate and return URLs

## Usage

```bash
# Search by query (auto-converts to hashtags)
python tiktok_search.py "tokyo travel itinerary"

# Use specific hashtags directly  
python tiktok_search.py --hashtags "tokyotravel,japantravel,tokyo"

# Limit results
python tiktok_search.py "tokyo travel" --max 30

# Save to JSON file
python tiktok_search.py "tokyo travel" -o results.json

# Local/dev mode (Mac) - tries direct search first
python tiktok_search.py --dev "tokyo travel"
```

## Output

```json
{
  "query": "tokyo travel itinerary",
  "hashtags": ["tokyotravelitinerary", "tokyo", "tokyotravel", ...],
  "count": 50,
  "urls": [
    "https://www.tiktok.com/@user/video/1234567890",
    ...
  ]
}
```

## Query to Hashtag Conversion

The script automatically converts search queries to relevant hashtags:

| Query | Generated Hashtags |
|-------|-------------------|
| "tokyo travel itinerary" | #tokyotravelitinerary, #tokyo, #tokyotravel, #japantravel |
| "best coffee new york" | #bestcoffeenewyork, #coffee, #newyork, #nycoffee |

## Cloud vs Local Modes

| Mode | Command | Behavior |
|------|---------|----------|
| Cloud (droplet) | `python tiktok_search.py` | Uses hashtag pages (bypass block) |
| Local (Mac) | `python tiktok_search.py --dev` | Tries direct search, falls back to hashtags |

## Performance

- ~4 seconds per hashtag
- ~30 videos per hashtag
- 50 videos typically requires 2 hashtags

## Files

```
/home/tiktok/search_experiments/
├── tiktok_search.py       # Main search script
├── venv/                  # Python environment  
├── browser_profiles/      # Persistent browser sessions
├── CLAUDE.md              # This file
└── *.json                 # Search results
```

## Dependencies

```bash
pip install zendriver aiohttp aiofiles
```

## Combining with Downloader

After searching, use the existing downloader to get the videos:

```bash
# Get search results
python tiktok_search.py "tokyo travel" -o results.json

# Extract URLs to file
cat results.json | jq -r '.urls[]' > urls.txt

# Download with the main downloader
cd /home/tiktok/download_experiments
python tiktok_downloader.py download --file urls.txt
```

## Limitations

1. **No direct search from datacenter**: TikTok blocks `/search/video` URLs from DigitalOcean/AWS IPs
2. **Hashtag approximation**: Results may not exactly match a direct search query
3. **Rate limiting**: Running too many requests may trigger blocks

## Troubleshooting

### Browser connection failed
Clear stale singleton files (done automatically on script start).

### No videos found
Try more specific or different hashtags using `--hashtags` flag.

### Results not relevant
Use `--hashtags` flag to specify exact hashtags manually.
