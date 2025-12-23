"""
TikTok video downloader using zendriver (undetectable Chrome automation).

This module handles:
- Browser session management (login persists)
- Video URL extraction from TikTok pages
- Video downloading
"""

import asyncio
import aiohttp
import aiofiles
import json
import re
from pathlib import Path
from typing import Optional

import zendriver as zd
from zendriver.core.config import Config

# Default profile directory for persistent sessions
DEFAULT_PROFILE_DIR = Path(__file__).parent / "browser_profile"


class TikTokDownloader:
    """
    Undetectable TikTok video downloader using zendriver.

    Usage:
        async with TikTokDownloader() as tt:
            await tt.download_video(url, output_path)
    """

    def __init__(
        self,
        profile_dir: Optional[Path] = None,
        headless: bool = False,
        local: bool = False,
    ):
        """
        Initialize the downloader.

        Args:
            profile_dir: Directory to store browser profile (for persistent login)
            headless: Run in headless mode (not recommended - more detectable)
            local: If True, auto-detect browser (for local dev). If False, use Docker paths.
        """
        self.profile_dir = profile_dir or DEFAULT_PROFILE_DIR
        self.headless = headless
        self.local = local
        self.browser: Optional[zd.Browser] = None
        self.page: Optional[zd.Tab] = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()

    async def start(self):
        """Start the browser."""
        self.profile_dir.mkdir(parents=True, exist_ok=True)

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
        self.browser = await zd.Browser.create(config)

        # Get the main page
        self.page = await self.browser.get("about:blank")

    async def stop(self):
        """Stop the browser."""
        if self.browser:
            await self.browser.stop()
            self.browser = None
            self.page = None

    async def is_logged_in(self) -> bool:
        """Check if we're logged into TikTok."""
        await self.page.get("https://www.tiktok.com")
        await asyncio.sleep(2)

        # Check for login indicators
        try:
            # If we can find the login button, we're not logged in
            login_btn = await self.page.find("Log in", timeout=3)
            return login_btn is None
        except:
            return True

    async def login_interactive(self):
        """
        Open TikTok login page for manual login.

        The browser will stay open until you complete login.
        Session is saved to profile_dir for future use.
        """
        print("Opening TikTok login page...")
        print("Please log in manually. Your session will be saved.")
        print("Press Enter in the terminal when done...")

        await self.page.get("https://www.tiktok.com/login")

        # Wait for user to complete login
        await asyncio.get_event_loop().run_in_executor(None, input)

        print("Login session saved!")

    async def download_video_via_canvas(self, tiktok_url: str, output_path: Path) -> dict:
        """
        Download video by capturing playback via canvas + MediaRecorder.

        This works by:
        1. Navigating to the TikTok page
        2. Waiting for the video to load
        3. Recording the video playback using canvas capture
        4. Triggering a native browser download
        """
        import shutil

        result = {"success": False, "video_path": None, "metadata": {}}

        # Clean the URL
        clean_url = tiktok_url.replace("\\", "").split("?")[0]

        # Set up download directory
        download_dir = Path("downloads").absolute()
        download_dir.mkdir(exist_ok=True)

        # Clear any existing files
        for f in download_dir.glob("tiktok_video*"):
            try:
                f.unlink()
            except:
                pass

        # Set download behavior via CDP
        await self.page.send(zd.cdp.browser.set_download_behavior(
            behavior="allow",
            download_path=str(download_dir)
        ))

        print(f"  Navigating to: {clean_url[:60]}...")
        await self.page.get(clean_url)

        print(f"  Waiting for video to load...")
        await asyncio.sleep(5)

        # Wait for video element
        for _ in range(15):
            has_video = await self.page.evaluate("!!document.querySelector('video')")
            if has_video:
                break
            await asyncio.sleep(1)

        # Get video info
        video_info = await self.page.evaluate("""
            (() => {
                const video = document.querySelector('video');
                if (!video) return { error: 'No video element' };
                return {
                    duration: video.duration || 60,
                    videoWidth: video.videoWidth || 720,
                    videoHeight: video.videoHeight || 1280,
                    readyState: video.readyState
                };
            })()
        """)

        if not video_info or video_info.get('error'):
            print(f"  Error: {video_info.get('error') if video_info else 'No video info'}")
            return result

        duration = video_info.get('duration') or 60
        width = video_info.get('videoWidth') or 720
        height = video_info.get('videoHeight') or 1280
        print(f"  Video found: {width}x{height}, {duration:.1f}s")

        # Get metadata while we're on the page
        result["metadata"] = await self.extract_metadata()

        # Start the capture process
        print(f"  Starting video capture (will take ~{duration:.0f}s)...")

        await self.page.evaluate("""
            (() => {
                window.__captureComplete = false;
                window.__captureError = null;
                window.__captureData = null;

                const video = document.querySelector('video');
                if (!video) {
                    window.__captureError = 'No video element';
                    window.__captureComplete = true;
                    return;
                }

                try {
                    // Capture directly from video element (requires --disable-web-security)
                    const stream = video.captureStream();
                    console.log('Got stream with', stream.getTracks().length, 'tracks');

                    const chunks = [];
                    const recorder = new MediaRecorder(stream, {
                        mimeType: 'video/webm',
                        videoBitsPerSecond: 5000000
                    });

                    recorder.ondataavailable = (e) => {
                        if (e.data.size > 0) chunks.push(e.data);
                    };

                    recorder.onstop = async () => {
                        const blob = new Blob(chunks, { type: 'video/webm' });
                        console.log('Capture complete, size:', blob.size);

                        // Convert blob to base64 for retrieval
                        try {
                            const buffer = await blob.arrayBuffer();
                            const bytes = new Uint8Array(buffer);
                            let binary = '';
                            const chunkSize = 32768;
                            for (let i = 0; i < bytes.length; i += chunkSize) {
                                binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
                            }
                            window.__captureData = btoa(binary);
                            window.__captureSize = blob.size;
                        } catch (e) {
                            window.__captureError = 'Base64 encode error: ' + e.message;
                        }

                        window.__captureComplete = true;
                    };

                    recorder.onerror = (e) => {
                        window.__captureError = e.message || 'Recorder error';
                        window.__captureComplete = true;
                    };

                    // Start from beginning
                    video.muted = true;  // Muted videos autoplay more reliably
                    video.currentTime = 0;
                    video.play().then(() => {
                        recorder.start(500);

                        const maxDuration = Math.min(video.duration * 1000 + 3000, 300000);

                        video.onended = () => {
                            if (recorder.state === 'recording') {
                                console.log('Video ended');
                                recorder.stop();
                            }
                        };

                        setTimeout(() => {
                            if (recorder.state === 'recording') {
                                console.log('Timeout reached');
                                recorder.stop();
                            }
                        }, maxDuration);
                    }).catch(e => {
                        window.__captureError = 'Play failed: ' + e.message;
                        window.__captureComplete = true;
                    });

                } catch (e) {
                    window.__captureError = 'Capture error: ' + e.message;
                    window.__captureComplete = true;
                }
            })()
        """)

        # Wait for capture to complete
        max_wait = int(duration) + 30
        for i in range(max_wait // 2):
            await asyncio.sleep(2)
            status = await self.page.evaluate(
                "({ complete: window.__captureComplete, error: window.__captureError })"
            )

            if i % 5 == 0:
                print(f"    Progress: {i*2}s / ~{duration:.0f}s")

            if status['complete']:
                break

        error = await self.page.evaluate("window.__captureError")
        if error:
            print(f"  Capture error: {error}")
            return result

        # Retrieve the captured video data from JavaScript
        print(f"  Retrieving captured video...")
        capture_size = await self.page.evaluate("window.__captureSize || 0")

        if capture_size > 10000:
            # Get base64 data in chunks to avoid memory issues
            import base64
            video_data = await self.page.evaluate("window.__captureData")

            if video_data:
                # Decode base64 and save
                video_bytes = base64.b64decode(video_data)

                # Ensure output path has correct extension
                if output_path.suffix.lower() != '.webm':
                    output_path = output_path.with_suffix('.webm')

                output_path.parent.mkdir(parents=True, exist_ok=True)

                async with aiofiles.open(output_path, 'wb') as f:
                    await f.write(video_bytes)

                result["success"] = True
                result["video_path"] = output_path
                print(f"  ✓ Video captured ({len(video_bytes) / 1024 / 1024:.1f} MB)")
            else:
                print(f"  No video data captured")
        else:
            print(f"  Captured video too small ({capture_size} bytes)")

        return result

    async def extract_video_url(self, tiktok_url: str) -> Optional[str]:
        """
        Extract the direct video URL from a TikTok page.

        Returns the video URL or None if extraction failed.
        """
        # Clean the URL
        clean_url = tiktok_url.replace("\\", "").split("?")[0]

        print(f"  Navigating to: {clean_url[:50]}...")
        await self.page.get(clean_url)

        # Wait for page to fully load
        print(f"  Waiting for page to load...")
        await asyncio.sleep(2)

        # Wait for video element to appear
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                has_video = await self.page.evaluate("!!document.querySelector('video')")
                if has_video:
                    print(f"  Video element found")
                    break
            except:
                pass
            await asyncio.sleep(1)
        else:
            print(f"  Warning: Video element not found after {max_attempts}s")

        # Give the video time to start loading
        await asyncio.sleep(3)

        # Try multiple methods to extract video URL
        video_url = None

        # Method 1: Look in page source/scripts for video URL patterns (most reliable)
        try:
            page_source = await self.page.evaluate("document.documentElement.outerHTML")

            # TikTok embeds video URLs in JSON data
            patterns = [
                # playAddr and downloadAddr in JSON
                r'"playAddr":"([^"]+)"',
                r'"downloadAddr":"([^"]+)"',
                # Direct CDN URLs
                r'(https://v[0-9a-z-]+\.tiktokcdn\.com/[^"\'<>\s]+\.mp4[^"\'<>\s]*)',
                r'(https://[^"\'<>\s]*tiktokcdn[^"\'<>\s]*\.mp4[^"\'<>\s]*)',
            ]

            for pattern in patterns:
                matches = re.findall(pattern, page_source)
                if matches:
                    url = matches[0]
                    # Skip blob URLs
                    if url.startswith('blob:'):
                        continue
                    # Unescape unicode escapes
                    try:
                        video_url = url.encode().decode('unicode_escape')
                    except:
                        video_url = url
                    # Unescape HTML entities
                    video_url = video_url.replace('\\u002F', '/').replace('&amp;', '&')
                    print(f"  Found video URL via page source")
                    break
        except Exception as e:
            print(f"  Method 1 (page source) failed: {e}")

        # Method 2: Check network requests for video URLs
        if not video_url:
            try:
                video_url = await self.page.evaluate("""
                    (() => {
                        const entries = performance.getEntriesByType('resource');
                        for (const entry of entries) {
                            const name = entry.name;
                            if (name.includes('tiktokcdn') && name.includes('.mp4') && !name.startsWith('blob:')) {
                                return name;
                            }
                        }
                        return null;
                    })()
                """)
                if video_url:
                    print(f"  Found video URL via network requests")
            except Exception as e:
                print(f"  Method 2 (network) failed: {e}")

        # Method 3: Get video element src (often blob, but try anyway)
        if not video_url:
            try:
                src = await self.page.evaluate("""
                    (() => {
                        const video = document.querySelector('video');
                        if (video && video.src && !video.src.startsWith('blob:')) {
                            return video.src;
                        }
                        const source = document.querySelector('video source');
                        if (source && source.src && !source.src.startsWith('blob:')) {
                            return source.src;
                        }
                        return null;
                    })()
                """)
                if src:
                    video_url = src
                    print(f"  Found video URL via video element")
            except Exception as e:
                print(f"  Method 3 (video element) failed: {e}")

        # Method 4: Try to find in window.__NEXT_DATA__ or similar
        if not video_url:
            try:
                video_url = await self.page.evaluate("""
                    (() => {
                        // Check for Next.js data
                        const nextData = document.getElementById('__NEXT_DATA__');
                        if (nextData) {
                            const text = nextData.textContent;
                            const match = text.match(/"playAddr":"([^"]+)"/);
                            if (match) {
                                return match[1].replace(/\\\\u002F/g, '/');
                            }
                        }

                        // Check for SIGI_STATE
                        const sigiState = document.getElementById('SIGI_STATE');
                        if (sigiState) {
                            const text = sigiState.textContent;
                            const match = text.match(/"playAddr":"([^"]+)"/);
                            if (match) {
                                return match[1].replace(/\\\\u002F/g, '/');
                            }
                        }

                        return null;
                    })()
                """)
                if video_url:
                    video_url = video_url.encode().decode('unicode_escape')
                    print(f"  Found video URL via embedded data")
            except Exception as e:
                print(f"  Method 4 (embedded data) failed: {e}")

        if video_url and video_url.startswith('blob:'):
            print(f"  Warning: Only found blob URL, cannot download directly")
            return None

        return video_url

    async def extract_metadata(self) -> dict:
        """Extract video metadata from the current page."""
        try:
            metadata = await self.page.evaluate("""
                (() => {
                    const data = {
                        title: document.title,
                        url: window.location.href,
                    };

                    // Try to get author
                    const authorEl = document.querySelector('[data-e2e="browse-username"]');
                    if (authorEl) data.author = authorEl.textContent;

                    // Try to get description
                    const descEl = document.querySelector('[data-e2e="browse-video-desc"]');
                    if (descEl) data.description = descEl.textContent;

                    // Try to get stats
                    const likeEl = document.querySelector('[data-e2e="like-count"]');
                    if (likeEl) data.likes = likeEl.textContent;

                    const commentEl = document.querySelector('[data-e2e="comment-count"]');
                    if (commentEl) data.comments = commentEl.textContent;

                    return data;
                })()
            """)
            return metadata
        except:
            return {}

    async def get_browser_cookies(self) -> dict:
        """Get cookies from the browser session."""
        try:
            cookies = await self.page.evaluate("""
                (() => {
                    return document.cookie;
                })()
            """)
            # Parse cookie string into dict
            cookie_dict = {}
            if cookies:
                for item in cookies.split(';'):
                    if '=' in item:
                        key, value = item.strip().split('=', 1)
                        cookie_dict[key] = value
            return cookie_dict
        except:
            return {}

    async def download_video(
        self,
        tiktok_url: str,
        output_path: Path,
        extract_metadata: bool = True,
    ) -> dict:
        """
        Download a TikTok video.

        Args:
            tiktok_url: TikTok video URL
            output_path: Path to save the video (will be saved as .webm)
            extract_metadata: Whether to extract and return metadata

        Returns:
            Dict with video_path and optional metadata
        """
        # Use canvas-based capture (records video playback)
        return await self.download_video_via_canvas(tiktok_url, output_path)

    async def _download_via_browser(self, video_url: str, output_path: Path, result: dict) -> dict:
        """Fallback: download video using the browser itself."""
        try:
            print(f"  Attempting browser-based download...")

            # Use browser to fetch the video
            download_script = f"""
                (async () => {{
                    try {{
                        const response = await fetch("{video_url}", {{
                            credentials: 'include',
                            headers: {{
                                'Accept': '*/*',
                            }}
                        }});
                        if (!response.ok) return {{ error: 'Fetch failed: ' + response.status }};

                        const blob = await response.blob();
                        const buffer = await blob.arrayBuffer();
                        const bytes = new Uint8Array(buffer);
                        return {{ data: Array.from(bytes), size: bytes.length }};
                    }} catch (e) {{
                        return {{ error: e.toString() }};
                    }}
                }})()
            """

            download_result = await self.page.evaluate(download_script)

            if download_result and 'data' in download_result:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                video_bytes = bytes(download_result['data'])

                async with aiofiles.open(output_path, 'wb') as f:
                    await f.write(video_bytes)

                if output_path.exists() and output_path.stat().st_size > 10000:
                    result["success"] = True
                    result["video_path"] = output_path
                    print(f"  ✓ Video downloaded via browser ({len(video_bytes) / 1024 / 1024:.1f} MB)")
                else:
                    print(f"  Browser download too small")
            elif download_result and 'error' in download_result:
                print(f"  Browser download error: {download_result['error']}")
            else:
                print(f"  Browser download failed")

        except Exception as e:
            print(f"  Browser download error: {e}")

        return result


async def download_single(url: str, output_path: Path, profile_dir: Path = None) -> dict:
    """Convenience function to download a single video."""
    async with TikTokDownloader(profile_dir=profile_dir) as tt:
        return await tt.download_video(url, output_path)


async def download_batch(
    urls: list[str],
    output_dir: Path,
    max_concurrent: int = 2,
    profile_dir: Path = None,
    delay_between: float = 2.0,
) -> list[dict]:
    """
    Download multiple videos.

    Note: Uses a single browser instance to maintain session,
    but adds delays between downloads to appear more human-like.
    """
    results = []

    async with TikTokDownloader(profile_dir=profile_dir) as tt:
        for i, url in enumerate(urls):
            print(f"\n[{i+1}/{len(urls)}] Processing video...")

            # Generate output path
            url_hash = hash(url) % 100000
            output_path = output_dir / f"video_{i+1}_{url_hash}.webm"

            result = await tt.download_video(url, output_path)
            result["url"] = url
            results.append(result)

            # Human-like delay between videos
            if i < len(urls) - 1:
                delay = delay_between + (delay_between * 0.5 * (asyncio.get_event_loop().time() % 1))
                print(f"  Waiting {delay:.1f}s before next video...")
                await asyncio.sleep(delay)

    return results


async def download_batch_parallel(
    urls: list[str],
    output_dir: Path,
    max_concurrent: int = 4,
    profile_dir: Path = None,
    local: bool = False,
) -> list[dict]:
    """
    Download multiple videos in parallel using multiple browser tabs.

    Each video is processed in its own tab for true parallelism.
    Note: Canvas capture still requires sequential playback per tab,
    but multiple tabs can play videos simultaneously.

    Args:
        local: If True, auto-detect browser (for local dev). If False, use Docker paths.
    """
    import shutil

    output_dir.mkdir(parents=True, exist_ok=True)

    # Set up download directory
    download_dir = Path("downloads").absolute()
    download_dir.mkdir(exist_ok=True)

    profile_dir = profile_dir or DEFAULT_PROFILE_DIR
    profile_dir.mkdir(parents=True, exist_ok=True)

    print(f"Starting browser with {max_concurrent} parallel tabs...")

    # Build browser args
    browser_args = [
        "--disable-web-security",  # Required for video.captureStream() on CDN videos
        "--autoplay-policy=no-user-gesture-required",
    ]

    if not local:
        # Docker-specific args
        browser_args.extend([
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--disable-software-rasterizer",
        ])

    config = Config(
        headless=False,
        user_data_dir=str(profile_dir),
        sandbox=local,  # True for local, False for Docker/root
        browser_executable_path=None if local else "/usr/bin/chromium",
        browser_connection_timeout=2.0,  # Increased for Docker startup time
        browser_args=browser_args,
    )
    browser = await zd.Browser.create(config)

    # Set download behavior
    main_tab = await browser.get("about:blank")
    await main_tab.send(zd.cdp.browser.set_download_behavior(
        behavior="allow",
        download_path=str(download_dir)
    ))

    async def process_video(url: str, index: int) -> dict:
        """Process a single video in its own tab."""
        result = {"success": False, "video_path": None, "url": url, "metadata": {}}

        clean_url = url.replace("\\", "").split("?")[0]
        url_hash = hash(url) % 100000
        output_path = output_dir / f"video_{index+1}_{url_hash}.webm"

        # Create a new tab for this video
        target_id = await main_tab.send(zd.cdp.target.create_target(clean_url))
        await browser.update_targets()

        # Find the new tab
        tab = None
        for t in browser.tabs:
            if t.target.target_id == target_id:
                tab = t
                break

        if not tab:
            print(f"  [{index+1}] Failed to create tab")
            return result

        try:
            print(f"  [{index+1}] Loading: {clean_url[:50]}...")
            await asyncio.sleep(5)

            # Wait for video element
            for _ in range(15):
                has_video = await tab.evaluate("!!document.querySelector('video')")
                if has_video:
                    break
                await asyncio.sleep(1)

            # Wait for video to be ready to play (readyState >= 3 = HAVE_FUTURE_DATA)
            for _ in range(30):
                ready_state = await tab.evaluate("""
                    (() => {
                        const video = document.querySelector('video');
                        return video ? video.readyState : 0;
                    })()
                """)
                if ready_state >= 3:
                    break
                await asyncio.sleep(1)

            # Get video info
            video_info = await tab.evaluate("""
                (() => {
                    const video = document.querySelector('video');
                    if (!video) return { error: 'No video element' };
                    return {
                        duration: video.duration,
                        videoWidth: video.videoWidth,
                        videoHeight: video.videoHeight
                    };
                })()
            """)

            if video_info.get('error'):
                print(f"  [{index+1}] Error: {video_info['error']}")
                return result

            # None-safe extraction of video info (values can be None even if keys exist)
            duration = video_info.get('duration') or 60
            width = video_info.get('videoWidth') or 720
            height = video_info.get('videoHeight') or 1280
            print(f"  [{index+1}] Video: {width}x{height}, {duration:.1f}s")

            # Start video capture using video.captureStream() with base64 transfer
            await tab.evaluate("""
                (() => {
                    window.__captureComplete = false;
                    window.__captureError = null;
                    window.__captureData = null;
                    window.__captureSize = 0;

                    const video = document.querySelector('video');
                    if (!video) {
                        window.__captureError = 'No video element';
                        window.__captureComplete = true;
                        return;
                    }

                    // Wait for video to be ready before capturing
                    function waitForReady() {
                        return new Promise((resolve, reject) => {
                            if (video.readyState >= 3) {
                                resolve();
                                return;
                            }

                            let attempts = 0;
                            const maxAttempts = 30;

                            const checkReady = () => {
                                attempts++;
                                if (video.readyState >= 3) {
                                    resolve();
                                } else if (attempts >= maxAttempts) {
                                    reject(new Error('Video not ready after 30s'));
                                } else {
                                    setTimeout(checkReady, 1000);
                                }
                            };

                            video.oncanplay = () => resolve();
                            video.onerror = () => reject(new Error('Video load error'));
                            checkReady();
                        });
                    }

                    waitForReady().then(() => {
                        try {
                            // Capture directly from video element (requires --disable-web-security)
                            const stream = video.captureStream();
                            console.log('Got stream with', stream.getTracks().length, 'tracks');

                            const chunks = [];
                            const recorder = new MediaRecorder(stream, {
                                mimeType: 'video/webm',
                                videoBitsPerSecond: 5000000
                            });

                            recorder.ondataavailable = (e) => {
                                if (e.data.size > 0) chunks.push(e.data);
                            };

                            recorder.onstop = async () => {
                                const blob = new Blob(chunks, { type: 'video/webm' });
                                console.log('Capture complete, size:', blob.size);
                                window.__captureSize = blob.size;

                                // Convert blob to base64 for retrieval
                                try {
                                    const buffer = await blob.arrayBuffer();
                                    const bytes = new Uint8Array(buffer);
                                    let binary = '';
                                    const chunkSize = 32768;
                                    for (let i = 0; i < bytes.length; i += chunkSize) {
                                        binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
                                    }
                                    window.__captureData = btoa(binary);
                                } catch (e) {
                                    window.__captureError = 'Base64 encode error: ' + e.message;
                                }

                                window.__captureComplete = true;
                            };

                            recorder.onerror = (e) => {
                                window.__captureError = e.message || 'Recorder error';
                                window.__captureComplete = true;
                            };

                            // Start from beginning - pause first, seek, then play
                            video.muted = true;
                            video.pause();
                            video.currentTime = 0;

                            // Wait a moment for seek to complete
                            setTimeout(() => {
                                video.play().then(() => {
                                    recorder.start(500);

                                    const maxDuration = Math.min((video.duration || 60) * 1000 + 3000, 300000);

                                    video.onended = () => {
                                        if (recorder.state === 'recording') {
                                            console.log('Video ended');
                                            recorder.stop();
                                        }
                                    };

                                    setTimeout(() => {
                                        if (recorder.state === 'recording') {
                                            console.log('Timeout reached');
                                            recorder.stop();
                                        }
                                    }, maxDuration);
                                }).catch(e => {
                                    window.__captureError = 'Play failed: ' + e.message;
                                    window.__captureComplete = true;
                                });
                            }, 500);

                        } catch (e) {
                            window.__captureError = 'Capture error: ' + e.message;
                            window.__captureComplete = true;
                        }
                    }).catch(e => {
                        window.__captureError = 'Wait failed: ' + e.message;
                        window.__captureComplete = true;
                    });
                })()
            """)

            # Wait for capture
            max_wait = int(duration) + 30
            for i in range(max_wait // 2):
                await asyncio.sleep(2)
                status = await tab.evaluate(
                    "({ complete: window.__captureComplete, error: window.__captureError })"
                )
                if status['complete']:
                    break

            error = await tab.evaluate("window.__captureError")
            if error:
                print(f"  [{index+1}] Capture error: {error}")
                return result

            # Retrieve the captured video data from JavaScript via base64
            capture_size = await tab.evaluate("window.__captureSize || 0")

            if capture_size > 10000:
                import base64
                video_data = await tab.evaluate("window.__captureData")

                if video_data:
                    # Decode base64 and save
                    video_bytes = base64.b64decode(video_data)
                    output_path.parent.mkdir(parents=True, exist_ok=True)

                    async with aiofiles.open(output_path, 'wb') as f:
                        await f.write(video_bytes)

                    result["success"] = True
                    result["video_path"] = output_path
                    print(f"  [{index+1}] ✓ Captured ({len(video_bytes) / 1024 / 1024:.1f} MB)")
                else:
                    print(f"  [{index+1}] No video data captured")
            else:
                print(f"  [{index+1}] Captured video too small ({capture_size} bytes)")

        except Exception as e:
            print(f"  [{index+1}] Error: {e}")
        finally:
            # Close the tab
            try:
                await tab.close()
            except:
                pass

        return result

    # Process videos in batches of max_concurrent
    results = []
    for batch_start in range(0, len(urls), max_concurrent):
        batch_urls = urls[batch_start:batch_start + max_concurrent]
        batch_indices = range(batch_start, batch_start + len(batch_urls))

        print(f"\nProcessing batch {batch_start // max_concurrent + 1} ({len(batch_urls)} videos)...")

        # Run batch in parallel
        batch_tasks = [
            process_video(url, idx)
            for url, idx in zip(batch_urls, batch_indices)
        ]
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

        for r in batch_results:
            if isinstance(r, Exception):
                results.append({"success": False, "error": str(r)})
            else:
                results.append(r)

        # Delay between batches
        if batch_start + max_concurrent < len(urls):
            print(f"\nWaiting 5s before next batch...")
            await asyncio.sleep(5)

    await browser.stop()
    return results


# CLI for testing
if __name__ == "__main__":
    import sys

    async def main():
        if len(sys.argv) < 2:
            print("Usage: python tiktok.py <url> [output.mp4]")
            print("       python tiktok.py --login")
            sys.exit(1)

        if sys.argv[1] == "--login":
            async with TikTokDownloader() as tt:
                await tt.login_interactive()
        else:
            url = sys.argv[1]
            output = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("video.mp4")

            result = await download_single(url, output)
            print(f"\nResult: {result}")

    asyncio.run(main())
