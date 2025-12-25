#!/usr/bin/env python3
"""
TikTok Search - Extract video URLs using multiple methods

Methods (in order of preference):
1. Google Search (most relevant results, works from datacenter)
2. TikTok Hashtags (fallback, works everywhere)

Usage:
    python tiktok_search.py "tokyo travel itinerary"
    python tiktok_search.py --dev "tokyo travel"
    python tiktok_search.py --method hashtags "tokyo travel"
    python tiktok_search.py --hashtags "tokyotravel,japantravel"
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
        base = Path.home() / "download_experiments" / "browser_profiles"
        profile_dir = base / "worker_0"
    else:
        base = Path("/home/tiktok/search_experiments/browser_profiles")
        profile_dir = base / name

    profile_dir.mkdir(parents=True, exist_ok=True)
    for f in profile_dir.glob("Singleton*"):
        f.unlink()
    return profile_dir

def get_config(profile_name="search"):
    profile_dir = get_profile_dir(profile_name)
    
    if DEV_MODE:
        return Config(
            headless=False,
            user_data_dir=str(profile_dir),
            sandbox=True,
            browser_executable_path=None,
            browser_connection_timeout=15.0,
            browser_args=["--autoplay-policy=no-user-gesture-required"],
        )
    else:
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
            ],
        )

# ============================================================
# Google Search
# ============================================================

def extract_tiktok_urls(links: list) -> set:
    """Extract clean TikTok video URLs from a list of links."""
    video_urls = set()
    for link in links:
        match = re.search(r'(https://(?:www\.)?tiktok\.com/@[^/]+/video/\d+)', link)
        if match:
            video_urls.add(match.group(1))
    return video_urls

async def search_google(query: str, max_results: int = 50) -> list[str]:
    """
    Search Google for TikTok videos using multiple query formats.
    Combines results for better coverage.
    """
    config = get_config("google")
    browser = await zd.Browser.create(config)
    
    all_urls = set()
    
    try:
        tab = await browser.get("about:blank")
        
        # Multiple query formats for better coverage
        query_formats = [
            f'tiktok.com {query}',           # Broad search
            f'site:tiktok.com "{query}"',  # Exact phrase
            f'site:tiktok.com {query}',      # Site restricted
        ]
        
        for google_query in query_formats:
            if len(all_urls) >= max_results:
                break
                
            print(f"  Trying: {google_query[:50]}...", end=" ", flush=True)
            
            search_url = f"https://www.google.com/search?q={quote(google_query)}&num=50"
            await tab.get(search_url)
            await asyncio.sleep(3)
            
            # Check for captcha
            title = await tab.evaluate("document.title")
            if "unusual traffic" in title.lower():
                print("captcha!")
                continue
            
            # Scroll and collect
            for _ in range(3):
                links = await tab.evaluate("""
                    (() => {
                        const links = document.querySelectorAll('a');
                        return Array.from(links)
                            .map(a => a.href)
                            .filter(h => h.includes('tiktok.com'));
                    })()
                """)
                
                new_urls = extract_tiktok_urls(links)
                prev_count = len(all_urls)
                all_urls.update(new_urls)
                
                await tab.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1)
            
            print(f"{len(all_urls)} total")
        
        return list(all_urls)[:max_results]
    
    finally:
        await browser.stop()

# ============================================================
# Hashtag Search
# ============================================================

def query_to_hashtags(query: str) -> list[str]:
    """Convert a search query to relevant hashtags."""
    words = re.sub(r'[^a-zA-Z0-9\s]', '', query.lower()).split()
    
    hashtags = []
    
    full = ''.join(words)
    if len(full) <= 30:
        hashtags.append(full)
    
    for word in words:
        if len(word) > 2:
            hashtags.append(word)
    
    for i in range(len(words)):
        for j in range(i + 1, min(i + 3, len(words) + 1)):
            combo = ''.join(words[i:j])
            if len(combo) <= 25:
                hashtags.append(combo)
    
    if any(w in words for w in ['tokyo', 'japan', 'japanese']):
        hashtags.extend(['tokyotravel', 'japantravel', 'visitjapan'])
    if any(w in words for w in ['food', 'eat', 'restaurant', 'cafe']):
        hashtags.extend(['foodtok', 'foodie'])
    if any(w in words for w in ['travel', 'trip', 'itinerary', 'vacation']):
        hashtags.extend(['traveltok', 'travelguide'])
    
    seen = set()
    unique = []
    for h in hashtags:
        if h not in seen and len(h) > 2:
            seen.add(h)
            unique.append(h)
    
    return unique[:10]

async def get_hashtag_videos(tab, hashtag: str, max_videos: int = 30) -> list[str]:
    """Get video URLs from a hashtag page."""
    url = f"https://www.tiktok.com/tag/{hashtag}"
    print(f"  Fetching #{hashtag}...", end=" ", flush=True)
    
    await tab.get(url)
    await asyncio.sleep(4)
    
    title = await tab.evaluate("document.title")
    if "not available" in title.lower():
        print("blocked")
        return []
    
    video_urls = set()
    for _ in range(5):
        links = await tab.evaluate("""
            (() => {
                const links = document.querySelectorAll('a[href*="/video/"]');
                return Array.from(links).map(a => a.href);
            })()
        """)
        
        for link in links:
            if '/video/' in link:
                video_urls.add(link.split('?')[0])
        
        if len(video_urls) >= max_videos:
            break
        
        await tab.evaluate("window.scrollBy(0, 1000)")
        await asyncio.sleep(1)
    
    result = list(video_urls)[:max_videos]
    print(f"{len(result)} videos")
    return result

async def search_hashtags(hashtags: list[str], max_results: int = 50) -> list[str]:
    """Search TikTok using hashtag pages."""
    config = get_config("hashtags")
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

# ============================================================
# Main
# ============================================================

async def main():
    global DEV_MODE
    
    parser = argparse.ArgumentParser(description='Search TikTok for videos')
    parser.add_argument('query', nargs='?', help='Search query')
    parser.add_argument('--dev', action='store_true', help='Local/dev mode (Mac)')
    parser.add_argument('--method', choices=['google', 'hashtags', 'auto'], 
                        default='auto', help='Search method (default: auto)')
    parser.add_argument('--hashtags', '-t', help='Comma-separated hashtags')
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
    print(f"Mode: {'local/dev' if DEV_MODE else 'cloud'}")
    
    urls = []
    method_used = None
    
    if args.hashtags:
        hashtags = [h.strip().lstrip('#') for h in args.hashtags.split(',')]
        print(f"Method: hashtags")
        print(f"Hashtags: {', '.join(['#' + h for h in hashtags])}")
        print("-" * 60)
        urls = await search_hashtags(hashtags, max_results=args.max)
        method_used = 'hashtags'
    
    elif args.query:
        print(f"Query: {args.query}")
        
        if args.method == 'google' or args.method == 'auto':
            print(f"Method: google")
            print("-" * 60)
            urls = await search_google(args.query, max_results=args.max)
            method_used = 'google'
            
            # Supplement with hashtags if needed
            if args.method == 'auto' and len(urls) < args.max // 2:
                print(f"\nSupplementing with hashtags...")
                hashtags = query_to_hashtags(args.query)
                print(f"Hashtags: {', '.join(['#' + h for h in hashtags])}")
                hashtag_urls = await search_hashtags(hashtags, max_results=args.max)
                urls = list(set(urls) | set(hashtag_urls))[:args.max]
                method_used = 'google+hashtags'
        
        elif args.method == 'hashtags':
            hashtags = query_to_hashtags(args.query)
            print(f"Method: hashtags")
            print(f"Hashtags: {', '.join(['#' + h for h in hashtags])}")
            print("-" * 60)
            urls = await search_hashtags(hashtags, max_results=args.max)
            method_used = 'hashtags'
    
    print("\n" + "=" * 60)
    print(f"RESULTS ({len(urls)} videos via {method_used})")
    print("=" * 60)

    for i, url in enumerate(urls, 1):
        print(f"{i:3}. {url}")

    # Always save URLs to a text file (for tiktok_downloader.py)
    if args.output:
        output_path = Path(args.output)
    else:
        # Default: save to parent directory as search_results.txt
        output_path = Path(__file__).parent.parent / "search_results.txt"

    # Write simple text file (one URL per line)
    with open(output_path, 'w') as f:
        for url in urls:
            f.write(url + '\n')

    print(f"\nSaved to: {output_path}")
    print(f"Run: python tiktok_downloader.py download --file {output_path}")

    return urls

if __name__ == '__main__':
    asyncio.run(main())
