"""MiniMax H3 frame-count alignment (17n + 5 at 24 fps)."""

from __future__ import annotations


def h3_frame_count(duration_seconds: float, fps: int = 24) -> int:
    """Match the ComfyMathExpression in the original R2V graph.

    expression:
        max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17
    """
    if duration_seconds <= 0:
        raise ValueError("duration must be > 0")
    raw = max(5, round(float(duration_seconds) * fps))
    return int(raw + (5 - (raw % 17)) % 17)
