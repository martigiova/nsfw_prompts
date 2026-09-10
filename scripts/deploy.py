#!/usr/bin/env python3
"""Check / run the deploy path: volume bootstrap + serverless endpoint.

Usage:
  python scripts/deploy.py --check
  python scripts/deploy.py --bootstrap   # CPU pod, needs CONFIRM_BOOTSTRAP=1
  python scripts/deploy.py --provision    # template + endpoint
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REQUIRED_ENDPOINT = (
    "RUNPOD_API_KEY",
    "RUNPOD_NETWORK_VOLUME_ID",
    "DOCKER_IMAGE",
)
REQUIRED_AIRTABLE = ("AIRTABLE_TOKEN", "AIRTABLE_BASE_ID")
REQUIRED_S3 = (
    "BUCKET_ENDPOINT_URL",
    "BUCKET_ACCESS_KEY_ID",
    "BUCKET_SECRET_ACCESS_KEY",
    "BUCKET_NAME",
    "BUCKET_PUBLIC_URL_PREFIX",
)
REQUIRED_BOOTSTRAP = ("RUNPOD_API_KEY", "RUNPOD_NETWORK_VOLUME_ID")


def missing(keys: tuple[str, ...]) -> list[str]:
    return [key for key in keys if not os.environ.get(key)]


def check() -> int:
    groups = {
        "volume bootstrap (CPU pod)": REQUIRED_BOOTSTRAP,
        "serverless endpoint": REQUIRED_ENDPOINT,
        "Airtable": REQUIRED_AIRTABLE,
        "S3/R2 (Airtable Output)": REQUIRED_S3,
    }
    status = 0
    for title, keys in groups.items():
        absent = missing(keys)
        if absent:
            status = 1
            print(f"MISSING {title}: " + ", ".join(absent))
        else:
            print(f"OK      {title}")
    docker = os.environ.get("DOCKER_IMAGE", "")
    if docker and "youruser" in docker.lower():
        print("WARN    DOCKER_IMAGE still looks like a placeholder")
        status = 1
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--bootstrap", action="store_true")
    parser.add_argument("--provision", action="store_true")
    args = parser.parse_args()
    if not (args.check or args.bootstrap or args.provision):
        args.check = True

    code = 0
    if args.check:
        code = check()
    if args.bootstrap:
        absent = missing(REQUIRED_BOOTSTRAP)
        if absent:
            print("Cannot bootstrap, missing " + ", ".join(absent), file=sys.stderr)
            return 1
        from scripts.bootstrap_via_runpod import main as bootstrap_main

        code = bootstrap_main() or code
    if args.provision:
        absent = missing(REQUIRED_ENDPOINT)
        if absent:
            print("Cannot provision, missing " + ", ".join(absent), file=sys.stderr)
            return 1
        from scripts.provision_runpod import main as provision_main

        code = provision_main() or code
    return code


if __name__ == "__main__":
    raise SystemExit(main())
