#!/usr/bin/env python3
"""Create a RunPod serverless template + endpoint (requires RUNPOD_API_KEY)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API = "https://rest.runpod.io/v1"

# Exact enum values from POST /endpoints (wrong names are rejected).
GPU_TYPE_IDS = [
    "NVIDIA GeForce RTX 4090",
    "NVIDIA RTX A6000",
    "NVIDIA L40S",
    "NVIDIA A100 80GB PCIe",
]


def request(method: str, path: str, payload: dict | None = None) -> dict:
    api_key = os.environ.get("RUNPOD_API_KEY")
    if not api_key:
        raise SystemExit("Set RUNPOD_API_KEY")
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"RunPod {exc.code} {method} {path}: {body}") from exc


def worker_env() -> dict[str, str]:
    keys = (
        "MOTION_LORA_NAME",
        "SKIP_MOTION_LORA",
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
        "AIRTABLE_TOKEN",
        "AIRTABLE_BASE_ID",
        "AIRTABLE_TABLE_NAME",
        "BUCKET_ENDPOINT_URL",
        "BUCKET_ACCESS_KEY_ID",
        "BUCKET_SECRET_ACCESS_KEY",
        "BUCKET_NAME",
        "BUCKET_PUBLIC_URL_PREFIX",
        "BUCKET_REGION",
        "COMFY_ROOT",
        "COMFY_INPUT_DIR",
        "SKIP_VOLUME_CHECK",
    )
    env = {
        "MOTION_LORA_NAME": os.environ.get(
            "MOTION_LORA_NAME", "hmmotion_minimax-h3_epoch40.safetensors"
        ),
        "SKIP_MOTION_LORA": os.environ.get("SKIP_MOTION_LORA", "0"),
        "COMFY_ROOT": os.environ.get("COMFY_ROOT", "/ComfyUI"),
        "COMFY_INPUT_DIR": os.environ.get("COMFY_INPUT_DIR", "/ComfyUI/input"),
        "SKIP_VOLUME_CHECK": os.environ.get("SKIP_VOLUME_CHECK", "0"),
        "AIRTABLE_TABLE_NAME": os.environ.get("AIRTABLE_TABLE_NAME", "Generazioni"),
    }
    for key in keys:
        value = os.environ.get(key)
        if value:
            env[key] = value
    return env


def main() -> int:
    image = os.environ.get("DOCKER_IMAGE")
    volume = os.environ.get("RUNPOD_NETWORK_VOLUME_ID")
    if not image:
        print("Set DOCKER_IMAGE to your pushed worker image", file=sys.stderr)
        return 1
    if not volume:
        print(
            "Warning: RUNPOD_NETWORK_VOLUME_ID is empty. "
            "The endpoint will start without MiniMax weights.",
            file=sys.stderr,
        )

    template = request(
        "POST",
        "/templates",
        {
            "name": os.environ.get("RUNPOD_TEMPLATE_NAME", "minimax-h3-r2v-worker"),
            "imageName": image,
            "isServerless": True,
            "containerDiskInGb": int(os.environ.get("CONTAINER_DISK_GB", "40")),
            "volumeInGb": 0,
            "volumeMountPath": "/runpod-volume",
            "dockerStartCmd": ["/start-serverless.sh"],
            "env": worker_env(),
        },
    )
    print("Template:", json.dumps(template, indent=2))
    template_id = template.get("id") or template.get("templateId")
    if not template_id:
        print("Could not read template id from response", file=sys.stderr)
        return 1

    endpoint_body = {
        "name": os.environ.get("RUNPOD_ENDPOINT_NAME", "minimax-h3-r2v"),
        "templateId": template_id,
        "gpuTypeIds": GPU_TYPE_IDS,
        "gpuCount": 1,
        "workersMin": int(os.environ.get("WORKERS_MIN", "0")),
        "workersMax": int(os.environ.get("WORKERS_MAX", "2")),
        "idleTimeout": int(os.environ.get("IDLE_TIMEOUT", "120")),
        "executionTimeoutMs": int(os.environ.get("EXECUTION_TIMEOUT_MS", "1800000")),
        "scalerType": "QUEUE_DELAY",
        "scalerValue": 4,
        "flashboot": True,
    }
    if volume:
        endpoint_body["networkVolumeId"] = volume

    endpoint = request("POST", "/endpoints", endpoint_body)
    print("Endpoint:", json.dumps(endpoint, indent=2))
    endpoint_id = endpoint.get("id") or endpoint.get("endpointId")
    if endpoint_id:
        print(f"Airtable RUNPOD_ENDPOINT_ID={endpoint_id}")
        print(f"POST https://api.runpod.ai/v2/{endpoint_id}/run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
