"""Pick a Network Volume data center with Serverless GPU stock."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

CATALOG = "https://api.runpod.io/v2"
PREFERRED_GPU = "NVIDIA RTX PRO 6000 Blackwell Server Edition"
_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0}


def _get(path: str) -> dict:
    api_key = os.environ.get("RUNPOD_API_KEY")
    if not api_key:
        raise SystemExit("Set RUNPOD_API_KEY")
    req = urllib.request.Request(
        f"{CATALOG}{path}",
        headers={
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "minimax-r2v/1.0",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"RunPod catalog {exc.code} GET {path}: {body}") from exc


def volume_data_centers(payload: dict | None = None) -> set[str]:
    payload = payload if payload is not None else _get("/catalog/datacenters")
    out: set[str] = set()
    for item in payload.get("dataCenters") or []:
        types = item.get("networkVolumeTypes") or []
        if types:
            out.add(item["id"])
    return out


def gpu_datacenter_stock(gpu_id: str, payload: dict | None = None) -> dict[str, str]:
    payload = payload if payload is not None else _get(
        "/catalog/gpus?include=AVAILABILITY&product=SERVERLESS"
    )
    for gpu in payload.get("gpus") or []:
        if gpu.get("id") == gpu_id:
            return {
                item["id"]: str(item.get("availability") or "NONE")
                for item in gpu.get("dataCenters") or []
            }
    return {}


def pick_serverless_dc(
    gpu_id: str = PREFERRED_GPU,
    *,
    datacenters: dict | None = None,
    gpus: dict | None = None,
) -> str:
    """Choose a DC that can host a Network Volume and has Serverless stock.

    Rank: HIGH > MEDIUM > LOW. NONE is skipped. Prefer globalNetwork when tied.
    """
    dc_payload = datacenters if datacenters is not None else _get("/catalog/datacenters")
    volume_ok = volume_data_centers(dc_payload)
    global_net = {
        item["id"]
        for item in (dc_payload.get("dataCenters") or [])
        if item.get("globalNetwork")
    }
    stock = gpu_datacenter_stock(gpu_id, gpus)
    ranked: list[tuple[int, int, str]] = []
    for dc_id, availability in stock.items():
        score = _RANK.get(availability, 0)
        if score <= 0 or dc_id not in volume_ok:
            continue
        ranked.append((score, 1 if dc_id in global_net else 0, dc_id))
    if not ranked:
        raise SystemExit(
            f"No Network-Volume data center has Serverless stock for {gpu_id}"
        )
    ranked.sort(reverse=True)
    return ranked[0][2]
