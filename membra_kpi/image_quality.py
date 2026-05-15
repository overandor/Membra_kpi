"""Image quality, hashing, and duplicate detection helpers for MEMBRA.

These functions provide production-facing controls for image-to-listing ingestion:
- perceptual-ish average hash for duplicate screening
- SHA-256 content hash for exact identity
- quality score for listing readiness
- safe metadata extraction without preserving EXIF payloads

The module is dependency-light and uses Pillow only, matching the repo's current stack.
"""
from __future__ import annotations

import hashlib
import io
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageStat


@dataclass(frozen=True)
class ImageQualityReport:
    width: int
    height: int
    megapixels: float
    aspect_ratio: float
    orientation: str
    exact_sha256: str
    average_hash: str
    brightness: float
    contrast: float
    sharpness_proxy: float
    listing_quality_score: int
    quality_grade: str
    warnings: list[str]
    recommended_actions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def exact_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def average_hash(image: Image.Image, hash_size: int = 8) -> str:
    """Return a compact average hash suitable for near-duplicate comparison."""
    img = image.convert("L").resize((hash_size, hash_size))
    pixels = list(img.getdata())
    avg = sum(pixels) / len(pixels)
    bits = ''.join('1' if p >= avg else '0' for p in pixels)
    return f"{int(bits, 2):0{hash_size * hash_size // 4}x}"


def hamming_distance_hex(a: str, b: str) -> int:
    if not a or not b:
        return 999
    try:
        x = int(a, 16) ^ int(b, 16)
        return x.bit_count()
    except ValueError:
        return 999


def quality_grade(score: int) -> str:
    if score >= 88:
        return "A"
    if score >= 74:
        return "B"
    if score >= 60:
        return "C"
    if score >= 45:
        return "D"
    return "F"


def _sharpness_proxy(gray: Image.Image) -> float:
    """Small edge-energy proxy without numpy/opencv."""
    w, h = gray.size
    if w < 3 or h < 3:
        return 0.0
    small = gray.resize((min(160, w), min(160, h)))
    w, h = small.size
    px = small.load()
    total = 0.0
    count = 0
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            gx = abs(int(px[x + 1, y]) - int(px[x - 1, y]))
            gy = abs(int(px[x, y + 1]) - int(px[x, y - 1]))
            total += gx + gy
            count += 1
    return round(total / max(count, 1), 3)


def analyze_image_bytes(data: bytes) -> ImageQualityReport:
    if not data:
        raise ValueError("image data is empty")
    with Image.open(io.BytesIO(data)) as img:
        img.load()
        width, height = img.size
        rgb = img.convert("RGB")
        gray = rgb.convert("L")
        stat = ImageStat.Stat(gray)
        brightness = round(float(stat.mean[0]), 3)
        contrast = round(float(stat.stddev[0]), 3)
        sharpness = _sharpness_proxy(gray)
        ahash = average_hash(rgb)

    megapixels = round((width * height) / 1_000_000, 3) if width and height else 0.0
    aspect_ratio = round(width / height, 4) if height else 0.0
    orientation = "landscape" if width > height else "portrait" if height > width else "square"

    score = 40
    warnings: list[str] = []
    actions: list[str] = []

    if megapixels >= 2:
        score += 18
    elif megapixels >= 1:
        score += 12
    else:
        warnings.append("low_resolution")
        actions.append("Upload a clearer photo with at least 1 megapixel resolution.")

    if 45 <= brightness <= 215:
        score += 12
    else:
        warnings.append("poor_brightness")
        actions.append("Retake the photo with better lighting.")

    if contrast >= 28:
        score += 12
    else:
        warnings.append("low_contrast")
        actions.append("Use a photo where the asset stands out from the background.")

    if sharpness >= 14:
        score += 12
    elif sharpness >= 8:
        score += 7
    else:
        warnings.append("possible_blur")
        actions.append("Retake the photo without motion blur.")

    if 0.45 <= aspect_ratio <= 2.4:
        score += 6
    else:
        warnings.append("unusual_aspect_ratio")
        actions.append("Crop or retake the image so the listing subject is clearly visible.")

    score = max(0, min(100, score))
    if not actions:
        actions.append("Image is acceptable for a private listing draft; collect proof fields before publishing.")

    return ImageQualityReport(
        width=width,
        height=height,
        megapixels=megapixels,
        aspect_ratio=aspect_ratio,
        orientation=orientation,
        exact_sha256=exact_sha256(data),
        average_hash=ahash,
        brightness=brightness,
        contrast=contrast,
        sharpness_proxy=sharpness,
        listing_quality_score=score,
        quality_grade=quality_grade(score),
        warnings=warnings,
        recommended_actions=actions,
    )


def analyze_image_file(path: str | Path) -> ImageQualityReport:
    return analyze_image_bytes(Path(path).read_bytes())


def is_near_duplicate(hash_a: str, hash_b: str, threshold: int = 6) -> bool:
    return hamming_distance_hex(hash_a, hash_b) <= threshold
