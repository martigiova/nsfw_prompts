"""Minimal RunPod REST v1 client used by provision and volume bootstrap."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API = "https://rest.runpod.io/v1"


def request(method: str, path: str, payload: dict | None = None) -> dict:
    api_key = os.environ.get("RUNPOD_API_KEY")
    if not api_key:
        raise SystemExit("Set RUNPOD_API_KEY")
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "minimax-r2v/1.0",
        "Accept": "application/json",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"RunPod {exc.code} {method} {path}: {body}") from exc


def resolve_data_center(volume_id: str) -> str:
    """Pin pods/endpoints to the Network Volume's data center.

    RunPod rejects (or silently ignores) a volume attached from another region.
    """
    override = os.environ.get("RUNPOD_DATA_CENTER_ID", "").strip()
    if override:
        return override
    if not os.environ.get("RUNPOD_API_KEY"):
        return ""
    info = request("GET", f"/networkvolumes/{volume_id}")
    dc = (info.get("dataCenterId") or "").strip()
    size = info.get("size")
    if isinstance(size, int) and size < 80:
        print(
            f"Warning: volume {volume_id} is {size} GB. MiniMax H3 weights are "
            "~56 GB; use 100–150 GB so a truncated download can be retried.",
            file=sys.stderr,
        )
    return dc
