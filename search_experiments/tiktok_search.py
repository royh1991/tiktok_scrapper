#!/usr/bin/env python3
"""
TikTok Search - Extract video URLs from hashtag pages

Uses zendriver to browse TikTok hashtag pages and extract video URLs.
Note: Direct search is blocked from datacenter IPs, so we use hashtags instead.

Usage:
    # Cloud mode (droplet) - converts query to hashtags
    python tiktok_search.py "tokyo travel"
    
    # Local mode (Mac) - can use direct search
    python tiktok_search.py --dev "tokyo travel"
    
    # Use specific hashtags directly
    python tiktok_search.py --hashtags "tokyotravel,japantravel,tokyo"
    
    # Save results to file
    python tiktok_search.py "tokyo travel" -o results.json
"""
import asyncio
import argparse
import json
import re
from pathlib import Path
from urllib.parse import quote

import zendriver as zd
from zendriver.core.config import Config

# ============================================================
# Configuration
# ============================================================

DEV_MODE = False

def get_profile_dir(name="search"):
    if DEV_MODE:
        base = Path.home() / "search_experiments" / "browser_profiles"
    else:
        base = Path("/home/tiktok/search_experiments/browser_profiles")
    
    profile_dir = base / name
    profile_dir.mkdir(parents=True, exist_ok=True)
    
    # Clear stale singleton files
    for f in profile_dir.glob("Singleton*"):
        f.unlink()
    
    return profile_dir

def get_config(profile_name="search"):
    """Get browser config based on mode."""
    profile_dir = get_profile_dir(profile_name)
    
    if DEV_MODE:
        # Mac development mode
        return Config(
            headless=False,
            user_data_dir=str(profile_dir),
            sandbox=True,
            browser_executable_path=None,  # Auto-detect Chrome
            browser_connection_timeout=15.0,
            browser_args=["--autoplay-policy=no-user-gesture-required"],
        )
    else:
        # Cloud/droplet mode
        return Config(
            headless=False,
            user_data_dir=str(profile_dir),
            sandbox=False,
            browser_executable_path="/snap/bin/chromium",
            browser_connection_timeout=15.0,
            browser_args=[
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-software-rasterizer",
                "--disable-setuid-sandbox",
                "--autoplay-policy=no-user-gesture-required",
            ],
        )

# ============================================================
# Hashtag Extraction Functions
# ============================================================

def query_to_hashtags(query: str) -> list[str]:
    """
    Convert a search query to relevant hashtags.
    
    Examples:
        "tokyo travel itinerary" -> ["tokyotravel", "tokyo", "tokyoitinerary", "japantravel"]
        "best coffee shops new york" -> ["nycoffee", "newyorkcoffee", "coffeeshops", "nyccafe"]
    """
    # Clean the query
    words = re.sub(r'[^a-zA-Z0-9\s]', '', query.lower()).split()
    
    hashtags = []
    
    # Full query without spaces
    full = ''.join(words)
    if len(full) <= 30:
        hashtags.append(full)
    
    # Common travel/content combinations
    content_suffixes = ['travel', 'trip', 'itinerary', 'guide', 'tips', 'food', 'eats']
    location_prefixes = ['tokyo', 'japan', 'korea', 'nyc', 'newyork', 'paris', 'london', 'la', 'losangeles']
    
    # Add individual words
    for word in words:
        if len(word) > 2:
            hashtags.append(word)
    
    # Add combinations
    for i in range(len(words)):
        for j in range(i + 1, min(i + 3, len(words) + 1)):
            combo = ''.join(words[i:j])
            if len(combo) <= 25:
                hashtags.append(combo)
    
    # Add common related hashtags based on keywords
    if any(w in words for w in ['tokyo', 'japan', 'japanese']):
        hashtags.extend(['tokyotravel', 'japantravel', 'tokyo', 'visitjapan'])
    if any(w in words for w in ['food', 'eat', 'restaurant', 'cafe']):
        hashtags.extend(['foodtok', 'foodie'])
    if any(w in words for w in ['travel', 'trip', 'itinerary', 'vacation']):
        hashtags.extend(['traveltok', 'travelguide'])
    
    # Dedupe and return
    seen = set()
    unique = []
    for h in hashtags:
        if h not in seen and len(h) > 2:
            seen.add(h)
            unique.append(h)
    
    return unique[:10]  # Limit to 10 hashtags

async def get_hashtag_videos(tab, hashtag: str, max_videos: int = 30) -> list[str]:
    """Get video URLs from a hashtag page."""
    url = f"https://www.tiktok.com/tag/{hashtag}"
    print(f"  Fetching #{hashtag}...", end=" ")
    
    await tab.get(url)
    await asyncio.sleep(4)
    
    # Check if page loaded
    title = await tab.evaluate("document.title")
    if "not available" in title.lower():
        print("blocked")
        return []
    
    video_urls = set()
    scroll_count = 0
    max_scrolls = 5
    
    while len(video_urls) < max_videos and scroll_count < max_scrolls:
        # Extract video URLs
        links = await tab.evaluate("""
            (() => {
                const links = document.querySelectorAll('a[href*="/video/"]');
                return Array.from(links).map(a => a.href);
            })()
        """)
        
        for link in links:
            if '/video/' in link and 'tiktok.com' in link:
                clean_url = link.split('?')[0]
                video_urls.add(clean_url)
        
        if len(video_urls) >= max_videos:
            break
        
        # Scroll for more
        await tab.evaluate("window.scrollBy(0, 1000)")
        await asyncio.sleep(1)
        scroll_count += 1
    
    unique = list(video_urls)[:max_videos]
    print(f"{len(unique)} videos")
    return unique

# ============================================================
# Main Search Functions
# ============================================================

async def search_by_hashtags(hashtags: list[str], max_results: int = 50) -> list[str]:
    """Search TikTok using hashtag pages."""
    config = get_config()
    browser = await zd.Browser.create(config)
    
    all_urls = set()
    
    try:
        tab = await browser.get("about:blank")
        
        for hashtag in hashtags:
            if len(all_urls) >= max_results:
                break
            
            try:
                videos = await get_hashtag_videos(tab, hashtag, max_videos=30)
                all_urls.update(videos)
            except Exception as e:
                print(f"  Error with #{hashtag}: {e}")
        
        return list(all_urls)[:max_results]
    
    finally:
        await browser.stop()

async def search_direct(query: str, max_results: int = 50) -> list[str]:
    """Direct search (only works in dev mode / non-datacenter IPs)."""
    config = get_config()
    browser = await zd.Browser.create(config)
    
    try:
        tab = await browser.get("about:blank")
        
        search_url = f"https://www.tiktok.com/search/video?q={quote(query)}"
        print(f"Searching: {search_url}")
        
        await tab.get(search_url)
        await asyncio.sleep(5)
        
        # Check if blocked
        body_text = await tab.evaluate("document.body.innerText.substring(0, 200)")
        if "Page not available" in body_text:
            print("Direct search blocked, falling back to hashtags...")
            hashtags = query_to_hashtags(query)
            return await search_by_hashtags(hashtags, max_results)
        
        video_urls = set()
        scroll_count = 0
        max_scrolls = 10
        
        while len(video_urls) < max_results and scroll_count < max_scrolls:
            links = await tab.evaluate("""
                (() => {
                    const links = document.querySelectorAll('a[href*="/video/"]');
                    return Array.from(links).map(a => a.href);
                })()
            """)
            
            for link in links:
                if '/video/' in link and 'tiktok.com' in link:
                    clean_url = link.split('?')[0]
                    video_urls.add(clean_url)
            
            print(f"  Found {len(video_urls)} videos...", end="\r")
            
            if len(video_urls) >= max_results:
                break
            
            await tab.evaluate("window.scrollBy(0, 1000)")
            await asyncio.sleep(1.5)
            scroll_count += 1
        
        print()
        return list(video_urls)[:max_results]
    
    finally:
        await browser.stop()

# ============================================================
# Main
# ============================================================

async def main():
    global DEV_MODE
    
    parser = argparse.ArgumentParser(description='Search TikTok for videos')
    parser.add_argument('query', nargs='?', help='Search query (converted to hashtags)')
    parser.add_argument('--dev', action='store_true', help='Use local/dev mode (Mac)')
    parser.add_argument('--hashtags', '-t', help='Comma-separated hashtags to search directly')
    parser.add_argument('--max', type=int, default=50, help='Max results (default: 50)')
    parser.add_argument('--output', '-o', help='Output JSON file')
    args = parser.parse_args()
    
    if not args.query and not args.hashtags:
        parser.print_help()
        return
    
    DEV_MODE = args.dev
    
    print("=" * 60)
    print("TikTok Search")
    print("=" * 60)
    print(f"Mode: {'local/dev' if DEV_MODE else 'cloud (hashtag-based)'}")
    
    if args.hashtags:
        # Direct hashtag search
        hashtags = [h.strip().lstrip('#') for h in args.hashtags.split(',')]
        print(f"Hashtags: {', '.join(['#' + h for h in hashtags])}")
        print("-" * 60)
        urls = await search_by_hashtags(hashtags, max_results=args.max)
    elif args.query:
        # Query-based search
        print(f"Query: {args.query}")
        
        if DEV_MODE:
            # Try direct search first (may work on non-datacenter IPs)
            print("-" * 60)
            urls = await search_direct(args.query, max_results=args.max)
        else:
            # Convert to hashtags
            hashtags = query_to_hashtags(args.query)
            print(f"Hashtags: {', '.join(['#' + h for h in hashtags])}")
            print("-" * 60)
            urls = await search_by_hashtags(hashtags, max_results=args.max)
    
    print("\n" + "=" * 60)
    print(f"RESULTS ({len(urls)} videos)")
    print("=" * 60)
    
    for i, url in enumerate(urls, 1):
        print(f"{i:3}. {url}")
    
    # Save to file if requested
    if args.output:
        output_path = Path(args.output)
        result = {
            'query': args.query or f"hashtags: {args.hashtags}",
            'hashtags': hashtags if not args.hashtags else args.hashtags.split(','),
            'count': len(urls),
            'urls': urls
        }
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\nSaved to: {output_path}")
    
    return urls

if __name__ == '__main__':
    asyncio.run(main())
