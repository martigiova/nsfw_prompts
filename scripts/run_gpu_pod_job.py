#!/usr/bin/env python3
"""Run Airtable MiniMax jobs on a GPU Pod, then stop the GPU.

v1 pods honor dockerEntrypoint, so this bypasses the MiniMax image `/start.sh`.
The Network Volume keeps the weights. The pod is created for the queue and
deleted when Todo/Queued/Running are gone — no idle GPU cost.

Set CONFIRM_GPU_JOB=1. Pass --queue for every pending row, or --record rec...
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

from minimax_r2v.airtable import ACTIVE_STATUSES, AirtableClient
from scripts.provision_runpod import (
    DEFAULT_CONTAINER_DISK_GB,
    DEFAULT_DOCKER_IMAGE,
    GPU_TYPE_IDS,
    VOLUME_ENTRYPOINT,
    worker_env,
)
from scripts.runpod_http import request, resolve_data_center

HIGH_VRAM_GPU_TYPE_IDS = [
    "NVIDIA RTX PRO 6000 Blackwell Server Edition",
    "NVIDIA RTX PRO 6000 Blackwell Workstation Edition",
]


def _gpu_ids(*, data_center: str, high_vram: bool) -> list[str]:
    override = os.environ.get("RUNPOD_GPU_TYPE_IDS", "").strip()
    if override:
        return [item.strip() for item in override.split(",") if item.strip()]
    if high_vram:
        return list(HIGH_VRAM_GPU_TYPE_IDS)
    gpu_ids = list(GPU_TYPE_IDS)
    if data_center == "US-IL-1":
        gpu_ids = ["NVIDIA GeForce RTX 4090"] + [
            gpu for gpu in GPU_TYPE_IDS if gpu != "NVIDIA GeForce RTX 4090"
        ]
    return gpu_ids


def pending_need_high_vram(records: list[dict] | None) -> bool:
    for record in records or []:
        fields = record.get("fields") or {}
        video = fields.get("Video")
        if isinstance(video, list) and video:
            return True
    return False


def pod_body(record_id: str | None = None, *, high_vram: bool = False) -> dict:
    volume = os.environ.get("RUNPOD_NETWORK_VOLUME_ID", "")
    if not volume:
        raise SystemExit("Set RUNPOD_NETWORK_VOLUME_ID")
    env = worker_env()
    env["AIRTABLE_DRAIN"] = "1"
    env["PASSWORD"] = os.environ.get("PASSWORD", "minimax-r2v")
    if record_id:
        env["AIRTABLE_RECORD_ID"] = record_id
    data_center = resolve_data_center(volume)
    gpu_ids = _gpu_ids(data_center=data_center or "", high_vram=high_vram)
    body = {
        "name": os.environ.get("GPU_JOB_POD_NAME", "minimax-h3-r2v-job"),
        "imageName": os.environ.get("DOCKER_IMAGE", DEFAULT_DOCKER_IMAGE),
        "gpuTypeIds": gpu_ids,
        "gpuCount": 1,
        "cloudType": os.environ.get("GPU_JOB_CLOUD", "SECURE"),
        "containerDiskInGb": int(os.environ.get("CONTAINER_DISK_GB", str(DEFAULT_CONTAINER_DISK_GB))),
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


def _airtable() -> AirtableClient:
    return AirtableClient(
        token=os.environ["AIRTABLE_TOKEN"],
        base_id=os.environ["AIRTABLE_BASE_ID"],
        table=os.environ.get("AIRTABLE_TABLE_NAME", "Minimax"),
    )


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


def wait_for_queue(timeout: int) -> list[dict]:
    """Wait until no Todo/Queued/Running rows remain, then return all records."""
    client = _airtable()
    deadline = time.time() + timeout
    stable = 0
    last: list[dict] = []
    while time.time() < deadline:
        records = client.list_records()
        last = records
        snapshot = []
        active = []
        for record in records:
            fields = record.get("fields") or {}
            status = str(fields.get("Status") or "")
            row = {
                "id": record.get("id"),
                "Status": status,
                "Output": fields.get("Output"),
                "Errore": str(fields.get("Errore") or "")[:120],
            }
            snapshot.append(row)
            if status in ACTIVE_STATUSES:
                active.append(row)
        print(json.dumps({"active": len(active), "rows": snapshot}))
        if not active:
            stable += 1
            if stable >= 2:
                return records
        else:
            stable = 0
        time.sleep(20)
    raise SystemExit(f"Timed out waiting for Airtable queue to drain ({len(last)} records)")


def terminate(pod_id: str) -> None:
    request("DELETE", f"/pods/{pod_id}")
    print(f"Terminated GPU job pod {pod_id}")


def _queue_ok(records: list[dict]) -> bool:
    ok = True
    for record in records:
        fields = record.get("fields") or {}
        status = str(fields.get("Status") or "")
        if status in ACTIVE_STATUSES:
            ok = False
        if status == "Error":
            print(record.get("id"), fields.get("Errore") or "Error", file=sys.stderr)
            ok = False
        if status == "Done" and fields.get("Output"):
            print("Output:", record.get("id"), fields["Output"])
    return ok


def main() -> int:
    queue = "--queue" in sys.argv
    record_id = ""
    if "--record" in sys.argv:
        idx = sys.argv.index("--record")
        if idx + 1 < len(sys.argv):
            record_id = sys.argv[idx + 1]
    record_id = record_id or os.environ.get("AIRTABLE_RECORD_ID", "").strip()
    if not record_id and not queue:
        print("Pass --queue or --record rec...", file=sys.stderr)
        return 1
    high_vram = "--high-vram" in sys.argv
    pending: list[dict] = []
    if os.environ.get("AIRTABLE_TOKEN") and os.environ.get("AIRTABLE_BASE_ID"):
        try:
            pending = _airtable().list_pending()
        except Exception as exc:
            print(f"Could not list Airtable pending: {exc}", file=sys.stderr)
    if not high_vram:
        high_vram = pending_need_high_vram(pending)
    if os.environ.get("CONFIRM_GPU_JOB") != "1":
        print(json.dumps(pod_body(record_id or None, high_vram=high_vram), indent=2))
        print("Dry run. Set CONFIRM_GPU_JOB=1 to create the GPU pod.", file=sys.stderr)
        return 0

    body = pod_body(record_id or None, high_vram=high_vram)
    print("GPU types:", body["gpuTypeIds"])
    pod = request("POST", "/pods", body)
    pod = request("POST", "/pods", body)
    print("Pod:", json.dumps({k: pod.get(k) for k in ("id", "desiredStatus", "imageName", "dataCenterId")}, indent=2))
    pod_id = pod.get("id") or pod.get("podId")
    if not pod_id:
        print("Could not read pod id", file=sys.stderr)
        return 1
    timeout = int(os.environ.get("GPU_JOB_TIMEOUT", "3600" if queue or not record_id else "1800"))
    ok = False
    try:
        if queue or not record_id:
            records = wait_for_queue(timeout)
            ok = _queue_ok(records)
        else:
            fields = wait_for_output(record_id, timeout)
            records = [{"id": record_id, "fields": fields}]
            ok = bool(fields.get("Output") and str(fields.get("Status")) == "Done")
            if ok:
                print("Output:", fields["Output"])
            else:
                print(fields.get("Errore") or "Job did not write Output", file=sys.stderr)
    finally:
        try:
            terminate(pod_id)
        except SystemExit as exc:
            print(exc, file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
