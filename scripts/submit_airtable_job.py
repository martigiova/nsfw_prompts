#!/usr/bin/env python3
"""Create or reuse a Minimax row and POST it to RunPod /run (same as submit_job.js)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _airtable(method: str, path: str, payload: dict | None = None) -> dict:
    token = os.environ["AIRTABLE_TOKEN"]
    base = os.environ["AIRTABLE_BASE_ID"]
    table = os.environ.get("AIRTABLE_TABLE_NAME", "Minimax")
    url = f"https://api.airtable.com/v0/{base}/{urllib.parse.quote(table, safe='')}{path}"
    data = None if payload is None else json.dumps(payload).encode()
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "minimax-r2v/1.0",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.loads(response.read().decode())


def _runpod(method: str, url: str, payload: dict | None = None) -> dict:
    api_key = os.environ["RUNPOD_API_KEY"]
    data = None if payload is None else json.dumps(payload).encode()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "minimax-r2v/1.0",
        "Accept": "application/json",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"RunPod {exc.code} {method} {url}: {body}") from exc


def create_record(prompt: str, image_url: str, duration: float, aspect: str) -> str:
    fields: dict = {
        "Prompt": prompt,
        "Image": [{"url": image_url}],
        "Status": "Queued",
        "Duration": duration,
        "Aspect": aspect,
    }
    created = _airtable("POST", "", {"fields": fields, "typecast": True})
    return created["id"]


def submit(record_id: str) -> dict:
    endpoint = os.environ["RUNPOD_ENDPOINT_ID"]
    url = f"https://api.runpod.ai/v2/{endpoint}/run"
    return _runpod("POST", url, {"input": {"airtable_record_id": record_id}})


def poll(job_id: str, timeout: int) -> dict:
    endpoint = os.environ["RUNPOD_ENDPOINT_ID"]
    url = f"https://api.runpod.ai/v2/{endpoint}/status/{job_id}"
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        last = _runpod("GET", url)
        status = str(last.get("status") or "")
        print(json.dumps({"status": status, "delayTime": last.get("delayTime"), "executionTime": last.get("executionTime")}))
        if status in {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"}:
            return last
        time.sleep(20)
    raise SystemExit(f"Timed out waiting for job {job_id}: {json.dumps(last)[:500]}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", help="Existing Airtable record id")
    parser.add_argument("--prompt", default="The person from <Picture 1> looks at the camera, then smiles. One continuous shot, natural light.")
    parser.add_argument("--image", help="Public HTTPS image URL for the Image attachment")
    parser.add_argument("--duration", type=float, default=4)
    parser.add_argument("--aspect", default="9:16")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--no-wait", action="store_true")
    args = parser.parse_args()

    for key in ("RUNPOD_API_KEY", "RUNPOD_ENDPOINT_ID", "AIRTABLE_TOKEN", "AIRTABLE_BASE_ID"):
        if not os.environ.get(key):
            print(f"Set {key}", file=sys.stderr)
            return 1

    record_id = args.record
    if not record_id:
        if not args.image:
            print("Pass --image URL or --record", file=sys.stderr)
            return 1
        record_id = create_record(args.prompt, args.image, args.duration, args.aspect)
        print(f"Airtable record {record_id}")

    job = submit(record_id)
    print(json.dumps(job, indent=2))
    job_id = job.get("id")
    if not job_id:
        print("RunPod did not return a job id", file=sys.stderr)
        return 1
    if args.no_wait:
        return 0
    result = poll(job_id, args.timeout)
    print(json.dumps(result, indent=2)[:8000])
    if str(result.get("status")) != "COMPLETED":
        return 1
    output = (result.get("output") or {})
    if output.get("error"):
        print(output["error"], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
