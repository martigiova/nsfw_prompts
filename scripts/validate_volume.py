#!/usr/bin/env python3
"""Check that MiniMax H3 R2V weights exist on the Network Volume."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from minimax_r2v.volume import OPTIONAL, REQUIRED, find_weight, missing_weights  # noqa: E402


def main() -> int:
    if not os.environ.get("VOLUME_ROOT") and Path("/workspace/models").exists():
        os.environ.setdefault("VOLUME_ROOT", "/workspace")

    missing = []
    for rel in REQUIRED:
        path = find_weight(rel)
        if path:
            print(f"OK   {rel} ({path.stat().st_size / 1e9:.1f} GB) -> {path}")
        else:
            print(f"MISS {rel}")
            missing.append(rel)
    for rel in OPTIONAL:
        path = find_weight(rel)
        print(("OK   " if path else "OPT  ") + rel)
    if missing:
        print("Missing required weights. Run scripts/bootstrap_network_volume.sh", file=sys.stderr)
        return 1
    print("Volume has the MiniMax H3 R2V files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
