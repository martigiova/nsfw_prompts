"""Aspect-ratio to pixel size, matching ResolutionSelector (1 MP, multiple of 32)."""

from __future__ import annotations

import math
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


def parse_aspect(aspect: str) -> tuple[int, int]:
    key = aspect.strip().lower()
    if key in ASPECT_ALIASES:
        return ASPECT_ALIASES[key]
    match = re.search(r"(\d+)\s*[:x/]\s*(\d+)", key)
    if not match:
        raise ValueError(f"Unsupported aspect ratio: {aspect}")
    return int(match.group(1)), int(match.group(2))


def resolution_from_aspect(
    aspect: str,
    megapixels: float = 1.0,
    multiple: int = 32,
) -> tuple[int, int]:
    w_ratio, h_ratio = parse_aspect(aspect)
    scale = math.sqrt((megapixels * 1_000_000) / (w_ratio * h_ratio))
    width = max(multiple, int(round(w_ratio * scale / multiple) * multiple))
    height = max(multiple, int(round(h_ratio * scale / multiple) * multiple))
    return width, height
