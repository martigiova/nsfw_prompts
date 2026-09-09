#!/usr/bin/env python3
"""Run one Airtable MiniMax job on a GPU Pod.

v1 pods honor dockerEntrypoint, so this bypasses the MiniMax image `/start.sh`.
Set CONFIRM_GPU_JOB=1 and AIRTABLE_RECORD_ID (or pass --record).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.provision_runpod import GPU_TYPE_IDS, VOLUME_ENTRYPOINT, worker_env
from scripts.runpod_http import request, resolve_data_center


def pod_body(record_id: str) -> dict:
    volume = os.environ.get("RUNPOD_NETWORK_VOLUME_ID", "")
    if not volume:
        raise SystemExit("Set RUNPOD_NETWORK_VOLUME_ID")
    env = worker_env()
    env["AIRTABLE_RECORD_ID"] = record_id
    env["PASSWORD"] = os.environ.get("PASSWORD", "minimax-r2v")
    gpu_ids = list(GPU_TYPE_IDS)
    data_center = resolve_data_center(volume)
    # US-IL-1 has Serverless/pod 4090 stock; RTX PRO 6000 is not offered there.
    if data_center == "US-IL-1":
        gpu_ids = ["NVIDIA GeForce RTX 4090"] + [
            gpu for gpu in GPU_TYPE_IDS if gpu != "NVIDIA GeForce RTX 4090"
        ]
    body = {
        "name": os.environ.get("GPU_JOB_POD_NAME", "minimax-h3-r2v-job"),
        "imageName": os.environ.get("DOCKER_IMAGE", "ls250824/run-comfyui-minimax:08092026"),
        "gpuTypeIds": gpu_ids,
        "gpuCount": 1,
        "cloudType": os.environ.get("GPU_JOB_CLOUD", "SECURE"),
        "containerDiskInGb": int(os.environ.get("CONTAINER_DISK_GB", "250")),
        "volumeInGb": 0,
        "networkVolumeId": volume,
        "volumeMountPath": "/runpod-volume",
        "env": env,
        "dockerEntrypoint": ["/bin/bash", "-lc"],
        "dockerStartCmd": [VOLUME_ENTRYPOINT],
    }
    if data_center:
        body["dataCenterIds"] = [data_center]
    return body


def _airtable_record(record_id: str) -> dict:
    token = os.environ["AIRTABLE_TOKEN"]
    base = os.environ["AIRTABLE_BASE_ID"]
    table = os.environ.get("AIRTABLE_TABLE_NAME", "Minimax")
    url = (
        f"https://api.airtable.com/v0/{base}/"
        f"{urllib.parse.quote(table, safe='')}/{record_id}"
    )
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "minimax-r2v/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.loads(response.read().decode())


def wait_for_output(record_id: str, timeout: int) -> dict:
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        record = _airtable_record(record_id)
        fields = record.get("fields") or {}
        last = {
            "Status": fields.get("Status"),
            "Output": fields.get("Output"),
            "Errore": str(fields.get("Errore") or "")[:400],
        }
        print(json.dumps(last))
        status = str(fields.get("Status") or "")
        if status in {"Done", "Error"} or fields.get("Output"):
            return fields
        time.sleep(20)
    raise SystemExit(f"Timed out waiting for Airtable Output: {json.dumps(last)}")


def terminate(pod_id: str) -> None:
    request("DELETE", f"/pods/{pod_id}")
    print(f"Terminated GPU job pod {pod_id}")


def main() -> int:
    record_id = ""
    if "--record" in sys.argv:
        idx = sys.argv.index("--record")
        if idx + 1 < len(sys.argv):
            record_id = sys.argv[idx + 1]
    record_id = record_id or os.environ.get("AIRTABLE_RECORD_ID", "").strip()
    if not record_id:
        print("Pass --record rec... or set AIRTABLE_RECORD_ID", file=sys.stderr)
        return 1
    if os.environ.get("CONFIRM_GPU_JOB") != "1":
        print(json.dumps(pod_body(record_id), indent=2))
        print("Dry run. Set CONFIRM_GPU_JOB=1 to create the GPU pod.", file=sys.stderr)
        return 0

    body = pod_body(record_id)
    pod = request("POST", "/pods", body)
    print("Pod:", json.dumps({k: pod.get(k) for k in ("id", "desiredStatus", "imageName", "dataCenterId")}, indent=2))
    pod_id = pod.get("id") or pod.get("podId")
    if not pod_id:
        print("Could not read pod id", file=sys.stderr)
        return 1
    timeout = int(os.environ.get("GPU_JOB_TIMEOUT", "1800"))
    try:
        fields = wait_for_output(record_id, timeout)
    finally:
        try:
            terminate(pod_id)
        except SystemExit as exc:
            print(exc, file=sys.stderr)
    if fields.get("Output") and str(fields.get("Status")) == "Done":
        print("Output:", fields["Output"])
        return 0
    print(fields.get("Errore") or "Job did not write Output", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
