#!/usr/bin/env python3
"""
Test different OCR approaches to find the best cost/accuracy tradeoff.

This script tests:
1. Single frame at different resolutions
2. Grid layouts (2, 3, 5 frames)
3. Local OCR (EasyOCR) as free baseline
4. Different prompts

Run with: python test_ocr.py
"""

import base64
import io
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image

load_dotenv()

# Test frames - pick ones with known text
TEST_DIR = Path("/Users/rhu/projects/tiktok_scrapper/output/20251222_215357_8f562cda/frames")
TEST_FRAMES = ["frame_010.jpg", "frame_020.jpg", "frame_030.jpg", "frame_040.jpg"]

# Expected text (ground truth for comparison)
EXPECTED_TEXT = {
    "frame_010.jpg": ["Shellman", "VILLAGE", "Ginza", "47th Street", "03-6274-6029"],
    "frame_020.jpg": ["It's really"],
    "frame_030.jpg": ["ROLEX", "SUBMARINER", "REF.1680", "1972", "Rolexes", "Tudors"],
    "frame_040.jpg": ["blew all your money", "plane ticket"],
}


def resize_image(img: Image.Image, max_size: int) -> Image.Image:
    """Resize image keeping aspect ratio."""
    if max(img.size) <= max_size:
        return img
    ratio = max_size / max(img.size)
    new_size = (int(img.width * ratio), int(img.height * ratio))
    return img.resize(new_size, Image.Resampling.LANCZOS)


def image_to_base64(img: Image.Image, quality: int = 85) -> str:
    """Convert PIL Image to base64 JPEG."""
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality)
    return base64.standard_b64encode(buffer.getvalue()).decode("utf-8")


def create_grid(images: list[Image.Image], cols: int = 1) -> Image.Image:
    """Stack images into a grid."""
    if cols == 1:
        # Vertical stack
        gap = 4
        width = max(img.width for img in images)
        height = sum(img.height for img in images) + gap * (len(images) - 1)
        grid = Image.new('RGB', (width, height), (40, 40, 40))
        y = 0
        for img in images:
            grid.paste(img, (0, y))
            y += img.height + gap
        return grid
    else:
        # Grid layout
        rows = (len(images) + cols - 1) // cols
        gap = 4
        cell_w = max(img.width for img in images)
        cell_h = max(img.height for img in images)
        width = cell_w * cols + gap * (cols - 1)
        height = cell_h * rows + gap * (rows - 1)
        grid = Image.new('RGB', (width, height), (40, 40, 40))
        for i, img in enumerate(images):
            r, c = i // cols, i % cols
            x = c * (cell_w + gap)
            y = r * (cell_h + gap)
            grid.paste(img, (x, y))
        return grid


def estimate_tokens(img: Image.Image) -> int:
    """Rough estimate of Claude image tokens."""
    # Based on Anthropic docs: ~1 token per 750 pixels + 85 base
    pixels = img.width * img.height
    return int(pixels / 750) + 85


def score_result(result: str, frame: str) -> tuple[int, int]:
    """Score OCR result against expected text. Returns (found, total)."""
    expected = EXPECTED_TEXT.get(frame, [])
    if not expected:
        return (0, 0)

    result_lower = result.lower()
    found = sum(1 for text in expected if text.lower() in result_lower)
    return (found, len(expected))


def test_claude_ocr(images_b64: list[str], prompt: str, model: str = "claude-sonnet-4-20250514") -> tuple[str, float]:
    """Call Claude API and return (result, cost_estimate)."""
    import anthropic

    client = anthropic.Anthropic()

    content = []
    for img_b64 in images_b64:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}
        })
    content.append({"type": "text", "text": prompt})

    start = time.time()
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": content}]
    )
    elapsed = time.time() - start

    # Estimate cost (Sonnet: $3/1M input, $15/1M output)
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    if "haiku" in model:
        cost = (input_tokens * 0.25 + output_tokens * 1.25) / 1_000_000
    else:  # sonnet
        cost = (input_tokens * 3 + output_tokens * 15) / 1_000_000

    return response.content[0].text, cost, input_tokens, output_tokens, elapsed


def test_easyocr(img: Image.Image) -> str:
    """Run EasyOCR (free, local)."""
    try:
        import easyocr
    except ImportError:
        return "[EasyOCR not installed - pip install easyocr]"

    # Convert to numpy array
    import numpy as np
    img_array = np.array(img)

    reader = easyocr.Reader(['en', 'ja'], gpu=False, verbose=False)
    results = reader.readtext(img_array)

    return " | ".join([text for _, text, _ in results])


def run_tests():
    """Run all OCR tests and compare results."""

    print("=" * 60)
    print("OCR OPTIMIZATION TEST")
    print("=" * 60)

    # Load test frames
    frames = []
    for fname in TEST_FRAMES:
        path = TEST_DIR / fname
        if path.exists():
            frames.append((fname, Image.open(path).copy()))

    if not frames:
        print("ERROR: No test frames found!")
        return

    print(f"\nLoaded {len(frames)} test frames")
    for fname, img in frames:
        print(f"  {fname}: {img.size}")

    results = []

    # =========================================
    # TEST 1: EasyOCR baseline (FREE)
    # =========================================
    print("\n" + "=" * 60)
    print("TEST 1: EasyOCR (free, local)")
    print("=" * 60)

    try:
        import easyocr
        reader = easyocr.Reader(['en'], gpu=False, verbose=False)

        total_found, total_expected = 0, 0
        for fname, img in frames:
            import numpy as np
            img_array = np.array(img)
            ocr_results = reader.readtext(img_array)
            text = " | ".join([t for _, t, _ in ocr_results])
            found, expected = score_result(text, fname)
            total_found += found
            total_expected += expected
            print(f"\n{fname}:")
            print(f"  Found: {text[:100]}...")
            print(f"  Score: {found}/{expected}")

        results.append({
            "test": "EasyOCR (free)",
            "cost": 0,
            "accuracy": f"{total_found}/{total_expected}",
            "tokens": 0
        })
    except ImportError:
        print("EasyOCR not installed - skipping")

    # =========================================
    # TEST 2: Single frames at different sizes
    # =========================================
    print("\n" + "=" * 60)
    print("TEST 2: Single frame, different resolutions")
    print("=" * 60)

    # Just test ONE frame to save costs
    test_fname, test_img = frames[0]  # frame_010.jpg has lots of text

    for max_size in [512, 768, 1024]:
        print(f"\n--- Resolution: {max_size}px ---")

        resized = resize_image(test_img.copy(), max_size)
        tokens_est = estimate_tokens(resized)
        print(f"  Image size: {resized.size}, ~{tokens_est} tokens")

        img_b64 = image_to_base64(resized)
        prompt = "Extract ALL visible text from this image. Include signs, labels, subtitles, prices, phone numbers. List each text item found."

        try:
            result, cost, in_tok, out_tok, elapsed = test_claude_ocr([img_b64], prompt)
            found, expected = score_result(result, test_fname)
            print(f"  Result: {result[:150]}...")
            print(f"  Score: {found}/{expected}")
            print(f"  Cost: ${cost:.5f} ({in_tok} in, {out_tok} out)")
            print(f"  Time: {elapsed:.1f}s")

            results.append({
                "test": f"Single {max_size}px",
                "cost": cost,
                "accuracy": f"{found}/{expected}",
                "tokens": in_tok
            })
        except Exception as e:
            print(f"  Error: {e}")

    # =========================================
    # TEST 3: Grid layouts
    # =========================================
    print("\n" + "=" * 60)
    print("TEST 3: Grid layouts (all 4 frames)")
    print("=" * 60)

    for grid_size, max_width in [(2, 600), (4, 512)]:
        print(f"\n--- Grid: {grid_size} frames, {max_width}px wide ---")

        # Resize all frames
        resized_frames = [resize_image(img.copy(), max_width) for _, img in frames[:grid_size]]
        grid = create_grid(resized_frames)
        tokens_est = estimate_tokens(grid)
        print(f"  Grid size: {grid.size}, ~{tokens_est} tokens")

        img_b64 = image_to_base64(grid)

        if grid_size == 2:
            prompt = f"This image shows {grid_size} video frames stacked vertically. Extract ALL visible text from EACH frame. Format: Frame 1: [text] | Frame 2: [text]"
        else:
            prompt = f"This image shows {grid_size} video frames stacked vertically (top to bottom). Extract ALL visible text from EACH frame including subtitles, signs, labels. Format: F1: [text] | F2: [text] | F3: [text] | F4: [text]"

        try:
            result, cost, in_tok, out_tok, elapsed = test_claude_ocr([img_b64], prompt)

            # Score each frame
            total_found, total_expected = 0, 0
            for i, (fname, _) in enumerate(frames[:grid_size]):
                found, expected = score_result(result, fname)
                total_found += found
                total_expected += expected

            print(f"  Result: {result[:200]}...")
            print(f"  Score: {total_found}/{total_expected}")
            print(f"  Cost: ${cost:.5f} ({in_tok} in, {out_tok} out)")
            print(f"  Time: {elapsed:.1f}s")

            results.append({
                "test": f"Grid {grid_size}x1 @{max_width}px",
                "cost": cost,
                "accuracy": f"{total_found}/{total_expected}",
                "tokens": in_tok
            })
        except Exception as e:
            print(f"  Error: {e}")

    # =========================================
    # TEST 4: Haiku vs Sonnet
    # =========================================
    print("\n" + "=" * 60)
    print("TEST 4: Haiku vs Sonnet (single frame 768px)")
    print("=" * 60)

    resized = resize_image(test_img.copy(), 768)
    img_b64 = image_to_base64(resized)
    prompt = "Extract ALL visible text. Include signs, labels, subtitles. List each item."

    for model in ["claude-3-5-haiku-20241022"]:
        print(f"\n--- Model: {model} ---")
        try:
            result, cost, in_tok, out_tok, elapsed = test_claude_ocr([img_b64], prompt, model=model)
            found, expected = score_result(result, test_fname)
            print(f"  Result: {result[:150]}...")
            print(f"  Score: {found}/{expected}")
            print(f"  Cost: ${cost:.6f} ({in_tok} in, {out_tok} out)")
            print(f"  Time: {elapsed:.1f}s")

            results.append({
                "test": f"Haiku 768px",
                "cost": cost,
                "accuracy": f"{found}/{expected}",
                "tokens": in_tok
            })
        except Exception as e:
            print(f"  Error: {e}")

    # =========================================
    # SUMMARY
    # =========================================
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"\n{'Test':<25} {'Cost':>10} {'Accuracy':>12} {'Tokens':>10}")
    print("-" * 60)
    for r in results:
        cost_str = f"${r['cost']:.5f}" if r['cost'] > 0 else "FREE"
        print(f"{r['test']:<25} {cost_str:>10} {r['accuracy']:>12} {r['tokens']:>10}")

    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)
    print("""
Based on results, consider:

1. IF accuracy is critical and budget allows:
   - Single frame @ 768-1024px with Sonnet
   - ~$0.002-0.003 per frame

2. IF cost is critical:
   - EasyOCR (free) for most frames
   - Claude only for frames where EasyOCR fails
   - Or: Haiku @ 768px (~$0.0002 per frame)

3. HYBRID approach (recommended):
   - Run EasyOCR first (free)
   - Only send to Claude frames with detected text for refinement
   - Use Haiku for refinement to save cost
""")


if __name__ == "__main__":
    run_tests()
