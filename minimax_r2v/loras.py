"""Locate LoRA files on the Network Volume / ComfyUI trees."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_LORA_DIRS = (
    "/runpod-volume/models/loras",
    "/runpod-volume/ComfyUI/models/loras",
    "/workspace/models/loras",
    "/workspace/ComfyUI/models/loras",
    "/ComfyUI/models/loras",
    "/comfyui/models/loras",
)


def lora_search_dirs() -> list[Path]:
    extra = os.environ.get("LORA_DIR")
    dirs = [Path(extra)] if extra else []
    dirs.extend(Path(item) for item in DEFAULT_LORA_DIRS)
    return dirs


def lora_exists(name: str, search_dirs: list[Path] | None = None) -> bool:
    if not name:
        return False
    for folder in search_dirs if search_dirs is not None else lora_search_dirs():
        candidate = folder / name
        if candidate.is_file():
            return True
    return False
