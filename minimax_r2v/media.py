"""Download Airtable / HTTP media into the ComfyUI input folder."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import requests

from .payload import MediaRef

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str, fallback: str = "file.bin") -> str:
    base = Path(name or "").name
    cleaned = _UNSAFE.sub("_", base).strip("._")
    return cleaned or fallback


def unique_path(directory: Path, filename: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem, suffix = candidate.stem, candidate.suffix
    index = 1
    while True:
        alt = directory / f"{stem}_{index}{suffix}"
        if not alt.exists():
            return alt
        index += 1


def download_media(
    items: list[MediaRef],
    destination: str | Path,
    timeout: int = 120,
) -> list[tuple[MediaRef, str]]:
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    saved: list[tuple[MediaRef, str]] = []
    for index, item in enumerate(items):
        filename = safe_filename(item.filename or _name_from_url(item.url), f"{item.kind}_{index}")
        if item.kind == "image" and not Path(filename).suffix:
            filename += ".png"
        if item.kind == "video" and not Path(filename).suffix:
            filename += ".mp4"
        if item.kind == "audio" and not Path(filename).suffix:
            filename += ".wav"
        path = unique_path(dest, filename)
        _fetch(item.url, path, timeout=timeout)
        saved.append((item, path.name))
    return saved


def _name_from_url(url: str) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name
    return name or "download.bin"


def _fetch(url: str, dest: Path, timeout: int) -> None:
    headers = {"User-Agent": "minimax-r2v/1.0"}
    with requests.get(url, stream=True, timeout=timeout, headers=headers) as response:
        response.raise_for_status()
        with dest.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
