#!/usr/bin/env python3
"""
TikTok Video Downloader - Production Ready

Features:
- Search TikTok for a query and download all found videos
- Download from a list of URLs
- Parallel extraction with multiple browser workers
- Parallel HTTP downloads with cookie authentication
- Undetectable via zendriver (datacenter-safe)

Usage:
    # Download from URL file (production/droplet)
    python tiktok_downloader.py download --file urls.txt

    # Download on Mac (dev mode)
    python tiktok_downloader.py --dev download --file urls.txt

    # Download specific URLs
    python tiktok_downloader.py --dev download URL1 URL2 URL3

    # Search and download (note: search blocked from datacenter IPs)
    python tiktok_downloader.py --dev search "best tokyo bars" --limit 20
"""

import asyncio
import aiohttp
import aiofiles
import re
import time
import sys
import json
import argparse
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field, asdict
from urllib.parse import quote

import zendriver as zd
from zendriver.core.config import Config
import zendriver.cdp.network as cdp_network

# Global dev mode flag (set by CLI)
DEV_MODE = False

def get_profile_base():
    if DEV_MODE:
        return Path(__file__).parent / "browser_profiles"
    return Path("/home/tiktok/tiktok_scrapper/browser_profiles")

def get_output_dir():
    if DEV_MODE:
        return Path(__file__).parent / "output"
    return Path("/home/tiktok/tiktok_scrapper/output")


@dataclass
class VideoMetadata:
    video_id: str
    video_url: str
    creator: str
    creator_nickname: str
    caption: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VideoResult:
    url: str
    success: bool
    file_path: Optional[Path] = None
    file_size: int = 0
    error: Optional[str] = None
    metadata: Optional[VideoMetadata] = None


def extract_video_id(url: str) -> str:
    """Extract video ID from TikTok URL."""
    match = re.search(r'/video/(\d+)', url)
    return match.group(1) if match else ""


def extract_creator(url: str) -> str:
    """Extract @username from TikTok URL."""
    match = re.search(r'@([^/]+)', url)
    return f"@{match.group(1)}" if match else ""


class BrowserWorker:
    """Single browser instance for extraction."""
    
    def __init__(self, worker_id: int, profile_dir: Path):
        self.worker_id = worker_id
        self.profile_dir = profile_dir
        self.browser = None
        self.tab = None
        
    async def start(self):
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        for f in self.profile_dir.glob("Singleton*"):
            f.unlink()

        if DEV_MODE:
            # Mac development mode - auto-detect Chrome
            config = Config(
                headless=False,
                user_data_dir=str(self.profile_dir),
                sandbox=True,
                browser_executable_path=None,  # Auto-detect
                browser_connection_timeout=10.0,
                browser_args=[
                    "--autoplay-policy=no-user-gesture-required",
                ],
            )
        else:
            # Production mode - Linux/droplet
            config = Config(
                headless=False,
                user_data_dir=str(self.profile_dir),
                sandbox=False,
                browser_executable_path="/snap/bin/chromium",
                browser_connection_timeout=10.0,
                browser_args=[
                    "--no-sandbox",
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                    "--disable-software-rasterizer",
                    "--disable-setuid-sandbox",
                    "--autoplay-policy=no-user-gesture-required",
                ],
            )

        self.browser = await zd.Browser.create(config)
        self.tab = await self.browser.get("about:blank")
    
    async def stop(self):
        if self.browser:
            await self.browser.stop()
    
    async def extract_video(self, tiktok_url: str) -> Tuple[Optional[str], Dict[str, str], Dict[str, str]]:
        """Extract video URL, cookies, and metadata from a TikTok page."""
        clean_url = tiktok_url.strip().replace("\\", "").split("?")[0]

        await self.tab.send(cdp_network.enable())
        captured_urls = []

        async def on_response(event: cdp_network.ResponseReceived):
            url = event.response.url
            ct = event.response.headers.get("content-type", "")
            cl = event.response.headers.get("content-length", "0")

            is_video = (
                "video" in ct or
                (("tiktokcdn" in url or "byteicdn" in url or "ibytedtos" in url) and
                 ("/video" in url or "play" in url.lower()) and
                 not any(x in url for x in [".js", ".css", ".json", ".png", ".jpg", ".webp"]))
            )

            try:
                size = int(cl)
                if is_video and size > 100000:
                    captured_urls.append((url, size))
            except:
                if is_video:
                    captured_urls.append((url, 0))

        self.tab.add_handler(cdp_network.ResponseReceived, on_response)

        try:
            await self.tab.get(clean_url)

            for attempt in range(8):
                await asyncio.sleep(0.5)
                has_video = await self.tab.evaluate("!!document.querySelector('video')")
                if has_video:
                    await self.tab.evaluate("""
                        (() => {
                            const video = document.querySelector('video');
                            if (video) { video.muted = true; video.play().catch(() => {}); }
                        })()
                    """)
                    break

            await asyncio.sleep(3)

            try:
                result = await self.tab.send(cdp_network.get_all_cookies())
                cookies = {c.name: c.value for c in result}
            except:
                cookies = {}

            video_url = None
            if captured_urls:
                captured_urls.sort(key=lambda x: x[1], reverse=True)
                video_url = captured_urls[0][0]

            if not video_url:
                try:
                    html = await self.tab.evaluate("document.documentElement.outerHTML")
                    for url in re.findall(r'"playAddr"\s*:\s*"([^"]+)"', html):
                        if "blob:" not in url and ".js" not in url:
                            video_url = url.replace("\\u002F", "/")
                            break
                except:
                    pass

            # Extract metadata from page
            metadata = await self._extract_metadata()

            return video_url, cookies, metadata

        finally:
            self.tab.handlers.clear()

    async def _extract_metadata(self) -> Dict[str, str]:
        """Extract caption and nickname from the current TikTok page."""
        try:
            # Get full page HTML for JSON extraction
            html = await self.tab.evaluate("document.documentElement.outerHTML")

            result = {'caption': '', 'nickname': ''}

            def decode_unicode(s: str) -> str:
                """Properly decode unicode escape sequences including emojis."""
                try:
                    # Handle \uXXXX sequences properly
                    return s.encode('utf-8').decode('unicode_escape').encode('latin-1').decode('utf-8')
                except:
                    try:
                        return s.encode('utf-8').decode('unicode_escape')
                    except:
                        return s

            # Method 1: Extract from embedded JSON in page source (most reliable)
            # Look for "desc" field (video description/caption)
            desc_match = re.search(r'"desc"\s*:\s*"([^"]{1,1000})"', html)
            if desc_match:
                result['caption'] = decode_unicode(desc_match.group(1))

            # Look for "nickname" field (creator display name)
            nick_match = re.search(r'"nickname"\s*:\s*"([^"]+)"', html)
            if nick_match:
                result['nickname'] = decode_unicode(nick_match.group(1))

            # Method 2: Fallback to DOM elements if JSON extraction failed
            if not result['caption']:
                dom_meta = await self.tab.evaluate("""
                    (() => {
                        const result = { caption: '' };

                        const captionEl = document.querySelector('[data-e2e="browse-video-desc"]') ||
                                         document.querySelector('[data-e2e="video-desc"]');
                        if (captionEl) {
                            result.caption = captionEl.innerText || '';
                        }

                        if (!result.caption) {
                            const metaDesc = document.querySelector('meta[name="description"]');
                            if (metaDesc) {
                                result.caption = metaDesc.content || '';
                            }
                        }

                        return result;
                    })()
                """)
                if dom_meta and not result['caption']:
                    result['caption'] = dom_meta.get('caption', '')

            return result
        except Exception as e:
            return {'caption': '', 'nickname': ''}
    
    async def search_tiktok(self, query: str, limit: int = 20) -> List[str]:
        """Search TikTok and return video URLs."""
        search_url = f"https://www.tiktok.com/search?q={quote(query)}"
        
        await self.tab.get(search_url)
        await asyncio.sleep(3)
        
        # Scroll to load more videos
        urls = set()
        max_scrolls = (limit // 10) + 3
        
        for scroll in range(max_scrolls):
            # Extract video URLs from current page
            try:
                new_urls = await self.tab.evaluate("""
                    (() => {
                        const links = document.querySelectorAll('a[href*="/video/"]');
                        return Array.from(links).map(a => a.href).filter(h => h.includes('/video/'));
                    })()
                """)
                
                for url in new_urls:
                    if '/video/' in url and url not in urls:
                        urls.add(url)
                        if len(urls) >= limit:
                            break
                
                if len(urls) >= limit:
                    break
                
                # Scroll down
                await self.tab.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1.5)
                
            except Exception as e:
                print(f"  Scroll {scroll+1} error: {e}")
                break
        
        return list(urls)[:limit]


class TikTokDownloader:
    def __init__(
        self,
        output_dir: Optional[Path] = None,
        num_workers: int = 5,
        max_downloads: int = 10,
        max_retries: int = 2,
    ):
        self.output_dir = Path(output_dir) if output_dir else get_output_dir()
        self.num_workers = num_workers
        self.max_downloads = max_downloads
        self.max_retries = max_retries
        self.workers: List[BrowserWorker] = []
        self._http_session = None
        
    async def __aenter__(self):
        await self.start()
        return self
        
    async def __aexit__(self, *args):
        await self.stop()
        
    async def start(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Starting {self.num_workers} browser workers...")
        
        async def start_worker(i):
            worker = BrowserWorker(i, get_profile_base() / f"worker_{i}")
            await worker.start()
            return worker
        
        self.workers = await asyncio.gather(*[start_worker(i) for i in range(self.num_workers)])
        print(f"All {len(self.workers)} workers ready.")
        
        connector = aiohttp.TCPConnector(limit=self.max_downloads * 2)
        timeout = aiohttp.ClientTimeout(total=120, connect=30)
        self._http_session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        
    async def stop(self):
        if self._http_session:
            await self._http_session.close()
        await asyncio.gather(*[w.stop() for w in self.workers], return_exceptions=True)
    
    async def search(self, query: str, limit: int = 20) -> List[str]:
        """Search TikTok for videos matching query."""
        print(f"\nSearching TikTok for: \"{query}\" (limit: {limit})...")
        
        # Use first worker for search
        urls = await self.workers[0].search_tiktok(query, limit)
        
        print(f"Found {len(urls)} video URLs")
        return urls
    
    async def download(self, urls: List[str]) -> List[VideoResult]:
        """Download videos from URLs."""
        if not urls:
            print("No URLs to download")
            return []
        
        print(f"\n{'='*60}")
        print(f"Downloading {len(urls)} videos")
        print(f"Workers: {self.num_workers} | Output: {self.output_dir}")
        print(f"{'='*60}\n")
        
        # Create work queue
        queue = asyncio.Queue()
        for i, url in enumerate(urls):
            await queue.put((i, url))
        
        results_dict = {}
        
        # Phase 1: Extract URLs
        print("Phase 1: Extracting video URLs...")
        start_extract = time.time()
        
        async def worker_loop(worker: BrowserWorker):
            while True:
                try:
                    idx, url = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                try:
                    video_url, cookies, page_meta = await worker.extract_video(url)
                    status = "✓" if video_url else "✗"
                    print(f"  [W{worker.worker_id}] [{idx+1}/{len(urls)}] {status}")
                    results_dict[idx] = (idx, url, video_url, cookies, page_meta)
                except Exception as e:
                    print(f"  [W{worker.worker_id}] [{idx+1}/{len(urls)}] Error: {e}")
                    results_dict[idx] = (idx, url, None, {}, {})
        
        await asyncio.gather(*[worker_loop(w) for w in self.workers])
        
        extract_time = time.time() - start_extract
        infos = [results_dict[i] for i in range(len(urls))]
        found = sum(1 for _, _, u, _, _ in infos if u)
        print(f"\nExtracted: {found}/{len(urls)} URLs ({extract_time:.1f}s)")

        # Phase 2: Download
        print("\nPhase 2: Downloading...")
        start_dl = time.time()

        async def download_one(idx, tiktok_url, video_url, cookies, page_meta):
            result = VideoResult(url=tiktok_url, success=False)

            # Extract video ID and creator from URL
            video_id = extract_video_id(tiktok_url)
            creator = extract_creator(tiktok_url)

            if not video_url:
                result.error = "No URL"
                return result

            if not video_id:
                result.error = "Could not extract video ID"
                return result

            # Create folder for this video
            video_folder = self.output_dir / video_id
            video_folder.mkdir(parents=True, exist_ok=True)

            cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())

            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "Referer": "https://www.tiktok.com/",
                "Origin": "https://www.tiktok.com",
                "Cookie": cookie_str,
                "sec-fetch-dest": "video",
                "sec-fetch-mode": "no-cors",
            }

            video_path = video_folder / "video.mp4"
            metadata_path = video_folder / "metadata.json"

            try:
                async with self._http_session.get(video_url, headers=headers) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        if len(content) > 50000:
                            # Save video
                            async with aiofiles.open(video_path, 'wb') as f:
                                await f.write(content)

                            # Create metadata
                            metadata = VideoMetadata(
                                video_id=video_id,
                                video_url=tiktok_url,
                                creator=creator,
                                creator_nickname=page_meta.get('nickname', ''),
                                caption=page_meta.get('caption', ''),
                            )

                            # Save metadata.json
                            async with aiofiles.open(metadata_path, 'w') as f:
                                await f.write(json.dumps(metadata.to_dict(), indent=2, ensure_ascii=False))

                            result.success = True
                            result.file_path = video_path
                            result.file_size = len(content)
                            result.metadata = metadata
                        else:
                            result.error = "File too small"
                    else:
                        result.error = f"HTTP {resp.status}"
            except Exception as e:
                result.error = str(e)

            return result

        sem = asyncio.Semaphore(self.max_downloads)

        async def bounded_download(args):
            async with sem:
                return await download_one(*args)

        download_tasks = [bounded_download((i, u, vu, c, pm)) for i, u, vu, c, pm in infos]
        results = await asyncio.gather(*download_tasks)

        dl_time = time.time() - start_dl

        # Phase 3: Retry failed videos
        failed_indices = [i for i, r in enumerate(results) if not r.success]
        retry_count = 0

        while failed_indices and retry_count < self.max_retries:
            retry_count += 1
            print(f"\nPhase 3: Retry {retry_count}/{self.max_retries} - {len(failed_indices)} failed videos...")

            # Re-extract URLs for failed videos
            retry_queue = asyncio.Queue()
            for idx in failed_indices:
                await retry_queue.put((idx, urls[idx]))

            retry_results_dict = {}

            async def retry_worker_loop(worker: BrowserWorker):
                while True:
                    try:
                        idx, url = retry_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

                    try:
                        await asyncio.sleep(2)  # Small delay before retry
                        video_url, cookies, page_meta = await worker.extract_video(url)
                        status = "✓" if video_url else "✗"
                        print(f"  [W{worker.worker_id}] Retry [{idx+1}] {status}")
                        retry_results_dict[idx] = (idx, url, video_url, cookies, page_meta)
                    except Exception as e:
                        print(f"  [W{worker.worker_id}] Retry [{idx+1}] Error: {e}")
                        retry_results_dict[idx] = (idx, url, None, {}, {})

            await asyncio.gather(*[retry_worker_loop(w) for w in self.workers])

            # Re-download retried videos
            retry_infos = [retry_results_dict[idx] for idx in failed_indices if idx in retry_results_dict]
            retry_download_tasks = [bounded_download(info) for info in retry_infos]
            retry_results = await asyncio.gather(*retry_download_tasks)

            # Update results with successful retries
            for info, retry_result in zip(retry_infos, retry_results):
                idx = info[0]
                if retry_result.success:
                    results[idx] = retry_result

            # Update failed indices for next retry round
            failed_indices = [i for i, r in enumerate(results) if not r.success]

        total_time = time.time() - start_extract

        # Summary
        print(f"\n{'='*60}")
        print("RESULTS")
        print(f"{'='*60}")
        
        ok_results = [r for r in results if r.success]
        total_size = sum(r.file_size for r in ok_results)
        
        print(f"Successful: {len(ok_results)}/{len(urls)}")
        print(f"Total size: {total_size/1024/1024:.2f}MB")
        print(f"Extract time: {extract_time:.1f}s")
        print(f"Download time: {dl_time:.1f}s")
        print(f"Total time: {total_time:.1f}s")
        print(f"Avg per video: {total_time/len(urls):.1f}s")
        print(f"Output: {self.output_dir}")
        
        return results


async def main():
    global DEV_MODE

    parser = argparse.ArgumentParser(description="TikTok Video Downloader")
    parser.add_argument("--dev", action="store_true", help="Dev mode (Mac, auto-detect Chrome)")
    parser.add_argument("--trip", help="Trip ID (uses trips/{trip_id}/videos/ structure)")
    parser.add_argument("--workers", type=int, default=5, help="Number of browser workers")
    parser.add_argument("--output", "-o", help="Output directory")
    parser.add_argument("--retries", type=int, default=2, help="Number of retries for failed videos (default: 2)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Search command
    search_parser = subparsers.add_parser("search", help="Search and download")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--limit", type=int, default=20, help="Max videos to download")

    # Download command
    dl_parser = subparsers.add_parser("download", help="Download from URLs")
    dl_parser.add_argument("--file", "-f", help="File containing URLs")
    dl_parser.add_argument("urls", nargs="*", help="URLs to download")

    args = parser.parse_args()

    DEV_MODE = args.dev
    if DEV_MODE:
        print("Running in DEV mode (Mac)")

    # Determine output directory and URL file based on --trip
    trip_dir = None
    if args.trip:
        if DEV_MODE:
            base_dir = Path(__file__).parent
        else:
            base_dir = Path("/home/tiktok/tiktok_scrapper")
        trip_dir = base_dir / "trips" / args.trip
        output_dir = trip_dir / "videos"
        print(f"Trip: {args.trip}")
    else:
        output_dir = Path(args.output) if args.output else None

    async with TikTokDownloader(
        output_dir=output_dir,
        num_workers=args.workers,
        max_retries=args.retries,
    ) as dl:
        if args.command == "search":
            urls = await dl.search(args.query, args.limit)
            if urls:
                await dl.download(urls)
        else:
            # Get URLs from file or args
            if args.file:
                content = open(args.file).read()
                print(f"Reading from file: {args.file} ({len(content)} chars)")
                try:
                    data = json.loads(content)
                    if isinstance(data, dict) and 'urls' in data:
                        urls = data['urls']
                    elif isinstance(data, list):
                        urls = data
                    else:
                        urls = []
                        print("JSON parsed but no 'urls' key or list found")
                except Exception as e:
                    print(f"JSON parse failed: {e}")
                    urls = [l.strip() for l in content.splitlines() if l.strip().startswith("http")]
            elif args.trip and (trip_dir / "urls.txt").exists():
                # Auto-read from trip's urls.txt
                content = open(trip_dir / "urls.txt").read()
                print(f"Auto-reading trip URLs: {trip_dir / 'urls.txt'} ({len(content)} chars)")
                try:
                    data = json.loads(content)
                    if isinstance(data, dict) and 'urls' in data:
                        urls = data['urls']
                    elif isinstance(data, list):
                        urls = data
                    else:
                        urls = []
                        print("JSON parsed but no 'urls' key or list found")
                except Exception as e:
                    print(f"JSON parse failed: {e}")
                    urls = [l.strip() for l in content.splitlines() if l.strip().startswith("http")]
                print(f"Loaded {len(urls)} URLs from {trip_dir / 'urls.txt'}")
            elif args.urls:
                urls = [u for u in args.urls if u.startswith("http")]
            else:
                urls = []

            if urls:
                await dl.download(urls)

                # Update trip metadata status
                if trip_dir:
                    metadata_path = trip_dir / "metadata.json"
                    if metadata_path.exists():
                        with open(metadata_path) as f:
                            metadata = json.load(f)
                        metadata["status"] = "downloaded"
                        with open(metadata_path, 'w') as f:
                            json.dump(metadata, f, indent=2)
            else:
                print("No URLs provided")


if __name__ == "__main__":
    asyncio.run(main())
