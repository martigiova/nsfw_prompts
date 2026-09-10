"""Locate MiniMax H3 weights on a RunPod Network Volume."""

from __future__ import annotations

import os
from pathlib import Path

from .weights import OPTIONAL, REQUIRED, expected_min_bytes

_SERVERLESS_ROOT = Path("/runpod-volume")


def model_roots() -> list[Path]:
    roots: list[Path] = []
    extra = os.environ.get("VOLUME_ROOT")
    if extra:
        volume = Path(extra)
        roots.extend([volume / "models", volume / "ComfyUI" / "models"])
    roots.extend(
        [
            _SERVERLESS_ROOT / "models",
            _SERVERLESS_ROOT / "ComfyUI" / "models",
            Path("/workspace") / "models",
            Path("/workspace") / "ComfyUI" / "models",
        ]
    )
    seen: set[Path] = set()
    unique: list[Path] = []
    for root in roots:
        if root not in seen:
            seen.add(root)
            unique.append(root)
    return unique


def volume_is_present() -> bool:
    """True when a Network Volume (or VOLUME_ROOT) is mounted."""
    if os.environ.get("VOLUME_ROOT"):
        return Path(os.environ["VOLUME_ROOT"]).exists()
    return _SERVERLESS_ROOT.exists() or Path("/workspace/models").exists()


def find_weight(rel: str, roots: list[Path] | None = None) -> Path | None:
    needed = expected_min_bytes(rel)
    for root in roots if roots is not None else model_roots():
        candidate = root / rel
        if candidate.is_file() and candidate.stat().st_size >= needed:
            return candidate
    return None


def missing_weights(roots: list[Path] | None = None) -> list[str]:
    search = roots if roots is not None else model_roots()
    return [rel for rel in REQUIRED if find_weight(rel, search) is None]


def describe_weights(roots: list[Path] | None = None) -> list[tuple[str, Path | None, int]]:
    """Return (rel, path, size) for required weights. path is None if missing."""
    search = roots if roots is not None else model_roots()
    rows: list[tuple[str, Path | None, int]] = []
    for rel in REQUIRED:
        path = find_weight(rel, search)
        size = path.stat().st_size if path else 0
        rows.append((rel, path, size))
    return rows


def log_volume_weights() -> None:
    """Print where each weight lives. Never downloads."""
    print("minimax-r2v: using Network Volume weights (no Hugging Face download)")
    for rel, path, size in describe_weights():
        if path:
            print(f"minimax-r2v: volume OK {rel} ({size / 1e9:.1f} GB) -> {path}")
        else:
            print(f"minimax-r2v: volume MISSING {rel}")
    for rel in OPTIONAL:
        path = find_weight(rel)
        if path:
            print(f"minimax-r2v: volume OPT {rel} ({path.stat().st_size / 1e9:.1f} GB) -> {path}")


def assert_weights_if_volume_present() -> None:
    if os.environ.get("SKIP_VOLUME_CHECK", "0") == "1":
        return
    if not volume_is_present():
        return
    log_volume_weights()
    missing = missing_weights()
    if missing:
        raise RuntimeError(
            "Network volume is missing MiniMax H3 weights: "
            + ", ".join(missing)
            + ". Run scripts/bootstrap_via_runpod.py or scripts/on_pod.sh."
        )
