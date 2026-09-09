#!/usr/bin/env python3
"""Create a Network Volume for MiniMax H3 if RUNPOD_NETWORK_VOLUME_ID is empty."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.runpod_http import request


def existing_named(name: str) -> dict | None:
    volumes = request("GET", "/networkvolumes")
    if not isinstance(volumes, list):
        return None
    for item in volumes:
        if item.get("name") == name:
            return item
    return None


def main() -> int:
    name = os.environ.get("RUNPOD_VOLUME_NAME", "minimax-h3")
    volume_id = os.environ.get("RUNPOD_NETWORK_VOLUME_ID", "").strip()
    if volume_id:
        info = request("GET", f"/networkvolumes/{volume_id}")
        print(json.dumps(info, indent=2))
        return 0
    found = existing_named(name)
    if found:
        print(json.dumps(found, indent=2))
        print(f"RUNPOD_NETWORK_VOLUME_ID={found['id']}")
        return 0
    body = {
        "name": name,
        "size": int(os.environ.get("RUNPOD_VOLUME_GB", "120")),
        "dataCenterId": os.environ.get("RUNPOD_DATA_CENTER_ID", "US-KS-2"),
    }
    created = request("POST", "/networkvolumes", body)
    print(json.dumps(created, indent=2))
    vid = created.get("id")
    if vid:
        print(f"RUNPOD_NETWORK_VOLUME_ID={vid}")
    return 0 if vid else 1


if __name__ == "__main__":
    raise SystemExit(main())
