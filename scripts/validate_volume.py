#!/usr/bin/env python3
"""Check that MiniMax H3 R2V weights exist on the Network Volume."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REQUIRED = [
    "diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors",
    "text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors",
    "vae/minimax_h3_video_vae_fp16.safetensors",
    "vae/minimax_h3_audio_vae_fp32.safetensors",
    "loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors",
]
OPTIONAL = [
    "loras/hmmotion_minimax-h3_epoch40.safetensors",
]


def roots() -> list[Path]:
    volume = Path(os.environ.get("VOLUME_ROOT", "/workspace"))
    return [
        volume / "models",
        volume / "ComfyUI" / "models",
        Path("/runpod-volume/models"),
        Path("/runpod-volume/ComfyUI/models"),
    ]


def find(rel: str) -> Path | None:
    for root in roots():
        candidate = root / rel
        if candidate.is_file() and candidate.stat().st_size > 1_000_000:
            return candidate
    return None


def main() -> int:
    missing = []
    for rel in REQUIRED:
        path = find(rel)
        if path:
            print(f"OK   {rel} ({path.stat().st_size / 1e9:.1f} GB) -> {path}")
        else:
            print(f"MISS {rel}")
            missing.append(rel)
    for rel in OPTIONAL:
        path = find(rel)
        print(("OK   " if path else "OPT  ") + rel)
    if missing:
        print("Missing required weights. Run scripts/bootstrap_network_volume.sh", file=sys.stderr)
        return 1
    print("Volume has the MiniMax H3 R2V files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
