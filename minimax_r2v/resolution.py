"""Aspect-ratio to pixel size, matching ResolutionSelector (multiple of 32).

Default is 1080p-class (~2.09 MP): 9:16 → 1088×1920, 16:9 → 1920×1088.
That is 1080×1920 snapped to MiniMax's 32px grid, not the old 1 MP 736×1344.
"""

from __future__ import annotations

import math
import os
import re

ASPECT_ALIASES = {
    "9:16": (9, 16),
    "9:16 (portrait widescreen)": (9, 16),
    "portrait": (9, 16),
    "16:9": (16, 9),
    "16:9 (landscape)": (16, 9),
    "landscape": (16, 9),
    "1:1": (1, 1),
    "square": (1, 1),
    "4:5": (4, 5),
    "3:4": (3, 4),
    "4:3": (4, 3),
    "2:3": (2, 3),
    "3:2": (3, 2),
    "21:9": (21, 9),
}

# 1088×1920 (9:16) / 1920×1088 (16:9) — 1080p snapped to 32px.
DEFAULT_MEGAPIXELS = 1088 * 1920 / 1_000_000


def parse_aspect(aspect: str) -> tuple[int, int]:
    key = aspect.strip().lower()
    if key in ASPECT_ALIASES:
        return ASPECT_ALIASES[key]
    match = re.search(r"(\d+)\s*[:x/]\s*(\d+)", key)
    if not match:
        raise ValueError(f"Unsupported aspect ratio: {aspect}")
    return int(match.group(1)), int(match.group(2))


def configured_megapixels() -> float:
    raw = os.environ.get("VIDEO_MEGAPIXELS", "").strip()
    if raw:
        return float(raw)
    return DEFAULT_MEGAPIXELS


def resolution_from_aspect(
    aspect: str,
    megapixels: float | None = None,
    multiple: int = 32,
) -> tuple[int, int]:
    if megapixels is None:
        megapixels = configured_megapixels()
    w_ratio, h_ratio = parse_aspect(aspect)
    scale = math.sqrt((megapixels * 1_000_000) / (w_ratio * h_ratio))
    width = max(multiple, int(round(w_ratio * scale / multiple) * multiple))
    height = max(multiple, int(round(h_ratio * scale / multiple) * multiple))
    return width, height
