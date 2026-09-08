"""Download MiniMax H3 weights onto a Network Volume."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from .weights import HF_REPO, REQUIRED_WEIGHTS, expected_min_bytes


def is_complete(path: Path, rel: str) -> bool:
    return path.is_file() and path.stat().st_size >= expected_min_bytes(rel)


def download_weights(
    volume_root: str | Path | None = None,
    hub_download: Callable | None = None,
) -> list[Path]:
    if hub_download is None:
        from huggingface_hub import hf_hub_download as hub_download

    root = Path(volume_root or os.environ.get("VOLUME_ROOT", "/workspace"))
    models = root / "models"
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    saved: list[Path] = []
    for weight in REQUIRED_WEIGHTS:
        dest = models / weight.rel
        if is_complete(dest, weight.rel):
            print(f"OK  already present: {dest} ({dest.stat().st_size / 1e9:.1f} GB)")
            saved.append(dest)
            continue
        if dest.exists():
            print(f"BAD truncated {dest} ({dest.stat().st_size} bytes), re-downloading")
            dest.unlink()
        print(f"DL  {HF_REPO}/{weight.repo_path}")
        downloaded = hub_download(
            repo_id=HF_REPO,
            filename=weight.repo_path,
            token=token,
            local_dir=str(models / ".hf-tmp"),
        )
        dest.parent.mkdir(parents=True, exist_ok=True)
        Path(downloaded).replace(dest)
        if not is_complete(dest, weight.rel):
            raise RuntimeError(
                f"downloaded {dest} is too small "
                f"({dest.stat().st_size} < {expected_min_bytes(weight.rel)})"
            )
        print(f"    -> {dest} ({dest.stat().st_size / 1e9:.1f} GB)")
        saved.append(dest)
    _link_aliases(models)
    return saved


def _link_aliases(models: Path) -> None:
    aliases = (
        (
            models / "diffusion_models" / "minimax_h3_ref2va_pruned_int8_convrot.safetensors",
            models / "unet" / "minimax_h3_ref2va_pruned_int8_convrot.safetensors",
        ),
        (
            models / "text_encoders" / "qwen3vl_32b_minimax_h3_int8_convrot.safetensors",
            models / "clip" / "qwen3vl_32b_minimax_h3_int8_convrot.safetensors",
        ),
    )
    for src, dest in aliases:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            if dest.is_symlink() or dest.exists():
                dest.unlink()
            dest.symlink_to(src)
