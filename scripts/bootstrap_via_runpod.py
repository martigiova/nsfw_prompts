#!/usr/bin/env python3
"""Populate a Network Volume with MiniMax H3 weights using a CPU Pod.

Does not need SSH or a GPU. Requires RUNPOD_API_KEY and RUNPOD_NETWORK_VOLUME_ID.
Set CONFIRM_BOOTSTRAP=1 to actually create the pod (it bills until we terminate it).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.runpod_http import request  # noqa: E402

DEFAULT_IMAGE = "runpod/base:1.1.0-ubuntu2204"
DEFAULT_REPO = "https://github.com/martigiova/nsfw_prompts.git"
HEALTH_PORT = 8888

BOOTSTRAP_SCRIPT = f"""set -euo pipefail
export VOLUME_ROOT=/workspace
export HF_HOME=/workspace/.hf
mkdir -p /workspace /var/minimax-bootstrap
printf '%s\\n' '{{"state":"starting"}}' > /var/minimax-bootstrap/status.json
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y git git-lfs python3-pip
git clone --depth 1 --branch "${{GIT_REF}}" "${{REPO_URL}}" /tmp/nsfw_prompts \\
  || git clone --depth 1 "$REPO_URL" /tmp/nsfw_prompts
bash /tmp/nsfw_prompts/scripts/on_pod.sh
python3 /tmp/nsfw_prompts/scripts/validate_volume.py
printf 'ok\\n' > /workspace/minimax-bootstrap.ok
printf '%s\\n' '{{"state":"ok"}}' > /var/minimax-bootstrap/status.json
python3 -m http.server {HEALTH_PORT} --bind 0.0.0.0 --directory /var/minimax-bootstrap
"""


def start_command() -> list[str]:
    return ["bash", "-lc", BOOTSTRAP_SCRIPT]


def pod_body() -> dict:
    volume = os.environ.get("RUNPOD_NETWORK_VOLUME_ID", "")
    if not volume:
        raise SystemExit("Set RUNPOD_NETWORK_VOLUME_ID")
    repo = os.environ.get("BOOTSTRAP_REPO", DEFAULT_REPO)
    git_ref = os.environ.get("GIT_REF", "cursor/minimax-runpod-serverless-9e74")
    return {
        "name": os.environ.get("BOOTSTRAP_POD_NAME", "minimax-h3-volume-bootstrap"),
        "imageName": os.environ.get("BOOTSTRAP_IMAGE", DEFAULT_IMAGE),
        "computeType": "CPU",
        "cpuFlavorIds": ["cpu3g", "cpu5g", "cpu3c"],
        "cloudType": os.environ.get("BOOTSTRAP_CLOUD", "SECURE"),
        "containerDiskInGb": int(os.environ.get("BOOTSTRAP_DISK_GB", "20")),
        "volumeInGb": 0,
        "networkVolumeId": volume,
        "volumeMountPath": "/workspace",
        "ports": [f"{HEALTH_PORT}/http"],
        "env": {
            "HF_TOKEN": os.environ.get("HF_TOKEN", ""),
            "HUGGING_FACE_HUB_TOKEN": os.environ.get("HF_TOKEN", ""),
            "REPO_URL": repo,
            "GIT_REF": git_ref,
        },
        "dockerStartCmd": start_command(),
    }



def _proxy_url(pod_id: str) -> str:
    return f"https://{pod_id}-{HEALTH_PORT}.proxy.runpod.net/status.json"


def wait_until_ok(pod_id: str, timeout: int = 7200) -> None:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        url = _proxy_url(pod_id)
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                last = response.read().decode("utf-8", errors="replace")
                data = json.loads(last)
                if data.get("state") == "ok":
                    print("Volume bootstrap finished:", last)
                    return
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
            last = str(exc)
        print("waiting for weights download...", last[:200])
        time.sleep(20)
    raise SystemExit(f"Timed out waiting for volume bootstrap on {pod_id}: {last}")


def terminate(pod_id: str) -> None:
    request("DELETE", f"/pods/{pod_id}")
    print(f"Terminated bootstrap pod {pod_id}")


def main() -> int:
    if os.environ.get("CONFIRM_BOOTSTRAP") != "1":
        body = pod_body()
        print(json.dumps(body, indent=2))
        print(
            "Dry run. Set CONFIRM_BOOTSTRAP=1 to create the CPU pod and download ~56 GB.",
            file=sys.stderr,
        )
        return 0

    body = pod_body()
    pod = request("POST", "/pods", body)
    print("Pod:", json.dumps(pod, indent=2))
    pod_id = pod.get("id") or pod.get("podId")
    if not pod_id:
        print("Could not read pod id", file=sys.stderr)
        return 1
    try:
        wait_until_ok(pod_id)
    finally:
        try:
            terminate(pod_id)
        except SystemExit as exc:
            print(exc, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
