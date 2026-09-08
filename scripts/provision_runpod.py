#!/usr/bin/env python3
"""Create a RunPod serverless template + endpoint (requires RUNPOD_API_KEY)."""

from __future__ import annotations

import json
import os
import sys
import urllib.request

API = "https://rest.runpod.io/v1"


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
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    image = os.environ.get("DOCKER_IMAGE")
    volume = os.environ.get("RUNPOD_NETWORK_VOLUME_ID")
    if not image:
        print("Set DOCKER_IMAGE to your pushed worker image", file=sys.stderr)
        return 1

    template = request(
        "POST",
        "/templates",
        {
            "name": "minimax-h3-r2v-worker",
            "imageName": image,
            "isServerless": True,
            "containerDiskInGb": 20,
            "volumeInGb": 0,
            "volumeMountPath": "/runpod-volume",
            "env": {
                "MOTION_LORA_NAME": os.environ.get(
                    "MOTION_LORA_NAME", "hmmotion_minimax-h3_epoch40.safetensors"
                ),
                "OPENROUTER_API_KEY": os.environ.get("OPENROUTER_API_KEY", ""),
                "AIRTABLE_TOKEN": os.environ.get("AIRTABLE_TOKEN", ""),
                "AIRTABLE_BASE_ID": os.environ.get("AIRTABLE_BASE_ID", ""),
                "AIRTABLE_TABLE_NAME": os.environ.get("AIRTABLE_TABLE_NAME", "Generazioni"),
                "BUCKET_ENDPOINT_URL": os.environ.get("BUCKET_ENDPOINT_URL", ""),
                "BUCKET_ACCESS_KEY_ID": os.environ.get("BUCKET_ACCESS_KEY_ID", ""),
                "BUCKET_SECRET_ACCESS_KEY": os.environ.get("BUCKET_SECRET_ACCESS_KEY", ""),
                "BUCKET_NAME": os.environ.get("BUCKET_NAME", ""),
                "BUCKET_PUBLIC_URL_PREFIX": os.environ.get("BUCKET_PUBLIC_URL_PREFIX", ""),
            },
        },
    )
    print("Template:", json.dumps(template, indent=2))
    template_id = template.get("id") or template.get("templateId")
    if not template_id:
        print("Could not read template id from response", file=sys.stderr)
        return 1

    endpoint_body = {
        "name": "minimax-h3-r2v",
        "templateId": template_id,
        "gpuTypeIds": [
            "NVIDIA RTX 4090",
            "NVIDIA A6000",
            "NVIDIA A100 80GB PCIe",
        ],
        "gpuCount": 1,
        "workersMin": 0,
        "workersMax": 2,
        "idleTimeout": 60,
        "executionTimeoutMs": 1800000,
        "scalerType": "QUEUE_DELAY",
        "scalerValue": 4,
        "flashboot": True,
    }
    if volume:
        endpoint_body["networkVolumeId"] = volume

    endpoint = request("POST", "/endpoints", endpoint_body)
    print("Endpoint:", json.dumps(endpoint, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
