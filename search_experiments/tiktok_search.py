#!/usr/bin/env python3
"""
TikTok Search - Google API based

Uses Serper API (serper.dev) for fast Google search results.
No browser needed - pure HTTP requests.
"""
import asyncio
import json
import re
import os
import time
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Load .env from parent directory (tiktok_scrapper/)
load_dotenv(Path(__file__).parent.parent / '.env')

SERPER_API_KEY = os.environ.get('SERPER_API_KEY')

def extract_tiktok_urls(results: list) -> list[str]:
    """Extract TikTok video URLs from search results."""
    urls = []
    pattern = r'https://(?:www\.)?tiktok\.com/@[\w.-]+/video/\d+'

    for result in results:
        link = result.get('link', '')
        match = re.search(pattern, link)
        if match:
            urls.append(match.group(0))

    return urls

async def google_search(query: str, num_results: int = 50) -> dict:
    """Search Google for TikTok videos using Serper API."""
    if not SERPER_API_KEY:
        raise ValueError("SERPER_API_KEY environment variable not set. Get one at serper.dev")

    start = time.time()
    all_urls = []

    search_query = f'tiktok {query}'
    pages_needed = (num_results + 9) // 10  # 10 results per page

    async with httpx.AsyncClient() as client:
        for page in range(1, pages_needed + 1):
            response = await client.post(
                'https://google.serper.dev/videos',
                headers={
                    'X-API-KEY': SERPER_API_KEY,
                    'Content-Type': 'application/json'
                },
                json={
                    'q': search_query,
                    'page': page
                },
                timeout=30.0
            )

            if response.status_code != 200:
                raise Exception(f"Serper API error: {response.status_code} - {response.text[:200]}")

            data = response.json()
            videos = data.get('videos', [])
            all_urls.extend(extract_tiktok_urls(videos))

            if len(all_urls) >= num_results or len(videos) < 10:
                break

    elapsed = time.time() - start

    # Deduplicate while preserving order
    seen = set()
    unique_urls = []
    for url in all_urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    return {
        'query': query,
        'count': len(unique_urls),
        'time': round(elapsed, 2),
        'urls': unique_urls[:num_results]
    }

async def main():
    import argparse

    parser = argparse.ArgumentParser(description='TikTok Search (Google API)')
    parser.add_argument('query', help='Search query')
    parser.add_argument('--max', type=int, default=50, help='Max results')
    parser.add_argument('--output', '-o', help='Output JSON file')
    args = parser.parse_args()

    print("=" * 60)
    print("TikTok Search (Google API)")
    print("=" * 60)
    print(f"Query: {args.query}")

    result = await google_search(args.query, num_results=args.max)

    print(f"\n→ {result['count']} videos in {result['time']}s")
    print("=" * 60)

    for i, url in enumerate(result['urls'], 1):
        print(f"{i:3}. {url}")

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\nSaved: {args.output}")

if __name__ == '__main__':
    asyncio.run(main())
