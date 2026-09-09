"""Download MiniMax H3 weights onto a Network Volume.

Streams bytes to disk. huggingface_hub is optional: a 27 GB file OOM-killed
a 16 GB CPU pod when the Hub client kept a second cache copy in RAM/disk.
"""

from __future__ import annotations

import os
import shutil
import urllib.request
from pathlib import Path
from typing import Callable

from .weights import HF_REPO, REQUIRED_WEIGHTS, expected_min_bytes

CHUNK = 8 * 1024 * 1024


def is_complete(path: Path, rel: str) -> bool:
    return path.is_file() and path.stat().st_size >= expected_min_bytes(rel)


def download_weights(
    volume_root: str | Path | None = None,
    hub_download: Callable | None = None,
) -> list[Path]:
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
        dest.parent.mkdir(parents=True, exist_ok=True)
        if hub_download is not None:
            downloaded = hub_download(
                repo_id=HF_REPO,
                filename=weight.repo_path,
                token=token,
                cache_dir=str(models / ".hf-cache"),
            )
            src = Path(downloaded).resolve()
            if src != dest:
                src.replace(dest)
        else:
            _stream_hf_file(weight.repo_path, dest, token)
        if not is_complete(dest, weight.rel):
            raise RuntimeError(
                f"downloaded {dest} is too small "
                f"({dest.stat().st_size} < {expected_min_bytes(weight.rel)})"
            )
        print(f"    -> {dest} ({dest.stat().st_size / 1e9:.1f} GB)")
        saved.append(dest)
        _cleanup_hub_cache(root, models)
    _link_aliases(models)
    _cleanup_hub_cache(root, models)
    return saved


def _stream_hf_file(repo_path: str, dest: Path, token: str | None) -> None:
    url = f"https://huggingface.co/{HF_REPO}/resolve/main/{repo_path}"
    part = dest.with_suffix(dest.suffix + ".part")
    headers = {"User-Agent": "minimax-r2v/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    existing = part.stat().st_size if part.is_file() else 0
    if existing:
        headers["Range"] = f"bytes={existing}-"
        print(f"    resume {existing / 1e9:.1f} GB")
    req = urllib.request.Request(url, headers=headers)
    mode = "ab" if existing else "wb"
    with urllib.request.urlopen(req, timeout=300) as response, part.open(mode) as handle:
        while True:
            chunk = response.read(CHUNK)
            if not chunk:
                break
            handle.write(chunk)
    part.replace(dest)


def _cleanup_hub_cache(volume_root: Path, models: Path) -> None:
    for path in (
        models / ".hf-cache",
        models / ".hf-tmp",
        volume_root / ".hf",
        Path(os.environ.get("HF_HOME", "/nonexistent")),
    ):
        if path.exists() and path.name in {".hf-cache", ".hf-tmp", ".hf"}:
            shutil.rmtree(path, ignore_errors=True)


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
