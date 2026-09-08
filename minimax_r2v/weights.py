"""Canonical MiniMax H3 R2V weight files (Hugging Face Comfy-Org/MiniMax-H3).

Sizes were read from the Hub API on 2026-09-08. A file smaller than min_bytes
is treated as truncated and must be re-downloaded.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

HF_REPO = "Comfy-Org/MiniMax-H3"


@dataclass(frozen=True)
class Weight:
    repo_path: str
    dest_dir: str
    size: int

    @property
    def filename(self) -> str:
        return Path(self.repo_path).name

    @property
    def rel(self) -> str:
        return f"{self.dest_dir}/{self.filename}"

    @property
    def min_bytes(self) -> int:
        return int(self.size * 0.98)


REQUIRED_WEIGHTS: tuple[Weight, ...] = (
    Weight(
        "diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors",
        "diffusion_models",
        20_970_379_616,
    ),
    Weight(
        "text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors",
        "text_encoders",
        27_141_342_152,
    ),
    Weight(
        "vae/minimax_h3_video_vae_fp16.safetensors",
        "vae",
        5_207_808_496,
    ),
    Weight(
        "vae/minimax_h3_audio_vae_fp32.safetensors",
        "vae",
        605_254_808,
    ),
    Weight(
        "loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors",
        "loras",
        1_956_193_000,
    ),
)

OPTIONAL = (
    "loras/hmmotion_minimax-h3_epoch40.safetensors",
)

REQUIRED = tuple(item.rel for item in REQUIRED_WEIGHTS)
MIN_BYTES = {item.rel: item.min_bytes for item in REQUIRED_WEIGHTS}


def expected_min_bytes(rel: str) -> int:
    return MIN_BYTES.get(rel, 1_000_000)
