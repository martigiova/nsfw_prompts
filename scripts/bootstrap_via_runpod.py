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

from scripts.runpod_http import request, resolve_data_center  # noqa: E402

DEFAULT_IMAGE = "runpod/base:1.1.0-ubuntu2204"
DEFAULT_REPO = "https://github.com/martigiova/nsfw_prompts.git"
HEALTH_PORT = 8888
TERMINAL_POD_STATUS = {"EXITED", "TERMINATED", "DEAD", "FAILED"}

BOOTSTRAP_SCRIPT = r"""set -euo pipefail
export VOLUME_ROOT=/workspace
export HF_HOME=/workspace/.hf
STATUS_DIR=/var/minimax-bootstrap
mkdir -p /workspace "$STATUS_DIR"
write_status() {
  python3 -c 'import json,sys; print(json.dumps({"state":sys.argv[1],"message":sys.argv[2][:2000]}))' "$1" "${2:-}" > "$STATUS_DIR/status.json"
}
serve() {
  exec python3 -m http.server 8888 --bind 0.0.0.0 --directory "$STATUS_DIR"
}
write_status starting "installing tools"
trap 'write_status error "bootstrap failed at line $LINENO"; serve' ERR
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y git git-lfs python3-pip
git clone --depth 1 --branch "${GIT_REF}" "${REPO_URL}" /workspace/nsfw_prompts \
  || git clone --depth 1 "$REPO_URL" /workspace/nsfw_prompts
bash /workspace/nsfw_prompts/scripts/on_pod.sh
python3 /workspace/nsfw_prompts/scripts/validate_volume.py
rm -rf /workspace/.hf /workspace/models/.hf-cache /workspace/models/.hf-tmp
printf 'ok\n' > /workspace/minimax-bootstrap.ok
write_status ok "weights ready"
serve
"""


def start_command() -> list[str]:
    return [BOOTSTRAP_SCRIPT]


def start_entrypoint() -> list[str]:
    return ["/bin/bash", "-lc"]


def interpret_status(status: dict | None, pod: dict | None) -> str:
    """Return 'ok', 'error', or 'wait'."""
    if status and status.get("state") == "ok":
        return "ok"
    if status and status.get("state") == "error":
        return "error"
    if pod:
        desired = str(pod.get("desiredStatus") or pod.get("desired_status") or "").upper()
        if desired in TERMINAL_POD_STATUS:
            return "error"
    return "wait"


def pod_body() -> dict:
    volume = os.environ.get("RUNPOD_NETWORK_VOLUME_ID", "")
    if not volume:
        raise SystemExit("Set RUNPOD_NETWORK_VOLUME_ID")
    repo = os.environ.get("BOOTSTRAP_REPO", DEFAULT_REPO)
    git_ref = os.environ.get("GIT_REF", "cursor/minimax-runpod-serverless-9e74")
    body = {
        "name": os.environ.get("BOOTSTRAP_POD_NAME", "minimax-h3-volume-bootstrap"),
        "imageName": os.environ.get("BOOTSTRAP_IMAGE", DEFAULT_IMAGE),
        "computeType": "CPU",
        "cpuFlavorIds": ["cpu3g", "cpu5g", "cpu3c"],
        "vcpuCount": int(os.environ.get("BOOTSTRAP_VCPU", "4")),
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
        "dockerEntrypoint": start_entrypoint(),
        "dockerStartCmd": start_command(),
    }
    data_center = resolve_data_center(volume)
    if data_center:
        body["dataCenterIds"] = [data_center]
    return body


def _proxy_url(pod_id: str) -> str:
    return f"https://{pod_id}-{HEALTH_PORT}.proxy.runpod.net/status.json"


def _read_status(pod_id: str) -> dict | None:
    url = _proxy_url(pod_id)
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, ValueError):
        return None


def _read_pod(pod_id: str) -> dict | None:
    try:
        return request("GET", f"/pods/{pod_id}")
    except SystemExit:
        return None


def wait_until_ok(pod_id: str, timeout: int = 7200) -> None:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        status = _read_status(pod_id)
        pod = _read_pod(pod_id)
        decision = interpret_status(status, pod)
        last = json.dumps(status or pod or {}, default=str)[:200]
        if decision == "ok":
            print("Volume bootstrap finished:", last)
            return
        if decision == "error":
            message = (status or {}).get("message") if status else last
            raise SystemExit(f"Volume bootstrap failed on {pod_id}: {message}")
        print("waiting for weights download...", last)
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
