#!/usr/bin/env python3
"""Create a RunPod serverless template + endpoint (requires RUNPOD_API_KEY)."""

from __future__ import annotations

import json
import os
import sys

from scripts.runpod_http import request, resolve_data_center

# Exact enum values from POST /endpoints (wrong names are rejected).
# Order is rent preference. RTX PRO 6000 (96 GB) is what we use for MiniMax
# in the GUI; 4090/A6000 remain fallbacks if PRO 6000 is out of stock.
GPU_TYPE_IDS = [
    "NVIDIA RTX PRO 6000 Blackwell Server Edition",
    "NVIDIA GeForce RTX 4090",
    "NVIDIA RTX A6000",
    "NVIDIA RTX 6000 Ada Generation",
    "NVIDIA L40S",
    "NVIDIA L40",
    "NVIDIA A40",
    "NVIDIA A100 80GB PCIe",
    "NVIDIA GeForce RTX 5090",
    "NVIDIA RTX A5000",
    "NVIDIA GeForce RTX 3090",
]


def worker_env() -> dict[str, str]:
    keys = (
        "MOTION_LORA_NAME",
        "SKIP_MOTION_LORA",
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
        "AIRTABLE_TOKEN",
        "AIRTABLE_BASE_ID",
        "AIRTABLE_TABLE_NAME",
        "AIRTABLE_PROMPT_FIELD",
        "AIRTABLE_IMAGE_FIELD",
        "AIRTABLE_VIDEO_FIELD",
        "AIRTABLE_AUDIO_FIELD",
        "AIRTABLE_DURATION_FIELD",
        "AIRTABLE_ASPECT_FIELD",
        "AIRTABLE_AUTO_PROMPT_FIELD",
        "AIRTABLE_STATUS_FIELD",
        "AIRTABLE_OUTPUT_FIELD",
        "AIRTABLE_ERROR_FIELD",
        "AIRTABLE_JOB_ID_FIELD",
        "BUCKET_ENDPOINT_URL",
        "BUCKET_ACCESS_KEY_ID",
        "BUCKET_SECRET_ACCESS_KEY",
        "BUCKET_NAME",
        "BUCKET_PUBLIC_URL_PREFIX",
        "BUCKET_REGION",
        "COMFY_ROOT",
        "COMFY_INPUT_DIR",
        "SKIP_VOLUME_CHECK",
        "COMFY_WAIT_TIMEOUT",
        "APP_ROOT",
    )
    env = {
        "MOTION_LORA_NAME": os.environ.get(
            "MOTION_LORA_NAME", "hmmotion_minimax-h3_epoch40.safetensors"
        ),
        "SKIP_MOTION_LORA": os.environ.get("SKIP_MOTION_LORA", "1"),
        "COMFY_ROOT": os.environ.get("COMFY_ROOT", "/ComfyUI"),
        "COMFY_INPUT_DIR": os.environ.get("COMFY_INPUT_DIR", "/ComfyUI/input"),
        "SKIP_VOLUME_CHECK": os.environ.get("SKIP_VOLUME_CHECK", "0"),
        "COMFY_WAIT_TIMEOUT": os.environ.get("COMFY_WAIT_TIMEOUT", "1650"),
        "AIRTABLE_TABLE_NAME": os.environ.get("AIRTABLE_TABLE_NAME", "Minimax"),
        "APP_ROOT": os.environ.get("APP_ROOT", "/runpod-volume/nsfw_prompts"),
    }
    for key in keys:
        value = os.environ.get(key)
        if value:
            env[key] = value
    return env


VOLUME_ENTRYPOINT = r"""set -euo pipefail
ROOT=""
for d in /runpod-volume/nsfw_prompts /workspace/nsfw_prompts; do
  if [ -d "$d/minimax_r2v" ]; then ROOT=$d; break; fi
done
if [ -z "$ROOT" ]; then
  echo "nsfw_prompts not found on the Network Volume"
  ls -la /runpod-volume /workspace || true
  exit 1
fi
export APP_ROOT="$ROOT"
if [ -d /runpod-volume/models ]; then export VOLUME_ROOT=/runpod-volume
elif [ -d /workspace/models ]; then export VOLUME_ROOT=/workspace
fi
if command -v git >/dev/null 2>&1 && [ -d "$ROOT/.git" ]; then
  git -C "$ROOT" fetch --depth 1 origin cursor/minimax-runpod-serverless-9e74 || true
  git -C "$ROOT" reset --hard FETCH_HEAD || true
fi
exec /bin/bash "$ROOT/worker/start_from_volume.sh"
"""


def template_body(image: str) -> dict:
    return {
        "name": os.environ.get("RUNPOD_TEMPLATE_NAME", "minimax-h3-r2v-worker"),
        "imageName": image,
        "isServerless": True,
        "containerDiskInGb": int(os.environ.get("CONTAINER_DISK_GB", "250")),
        "volumeInGb": int(os.environ.get("TEMPLATE_VOLUME_GB", "0")),
        "volumeMountPath": "/runpod-volume",
        "dockerEntrypoint": ["/bin/bash", "-lc", VOLUME_ENTRYPOINT],
        "dockerStartCmd": [],
        "env": worker_env(),
    }


def endpoint_body(template_id: str, volume: str) -> dict:
    body = {
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
        body["networkVolumeId"] = volume
        data_center = resolve_data_center(volume)
        if data_center:
            body["dataCenterIds"] = [data_center]
    return body


def _print_endpoint(endpoint: dict) -> str | None:
    print("Endpoint:", json.dumps(endpoint, indent=2))
    endpoint_id = endpoint.get("id") or endpoint.get("endpointId")
    if endpoint_id:
        print(f"Airtable RUNPOD_ENDPOINT_ID={endpoint_id}")
        print(f"POST https://api.runpod.ai/v2/{endpoint_id}/run")
    return endpoint_id


def patch_template(template_id: str, image: str) -> dict:
    """Resize container disk / env on the live serverless template."""
    return request("PATCH", f"/templates/{template_id}", template_body(image))


def patch_endpoint(endpoint_id: str, volume: str) -> dict:
    """Move an existing endpoint onto a (possibly new) Network Volume."""
    body: dict = {
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
        body["networkVolumeId"] = volume
        data_center = resolve_data_center(volume)
        if data_center:
            body["dataCenterIds"] = [data_center]
    return request("PATCH", f"/endpoints/{endpoint_id}", body)


def main() -> int:
    image = os.environ.get("DOCKER_IMAGE")
    volume = os.environ.get("RUNPOD_NETWORK_VOLUME_ID")
    update_id = os.environ.get("RUNPOD_ENDPOINT_ID", "").strip()
    if "--update" in sys.argv:
        update_id = update_id or os.environ.get("RUNPOD_ENDPOINT_ID", "").strip()
        if not update_id:
            print("Set RUNPOD_ENDPOINT_ID to PATCH an existing endpoint", file=sys.stderr)
            return 1
        if not volume:
            print("Set RUNPOD_NETWORK_VOLUME_ID", file=sys.stderr)
            return 1
        template_id = os.environ.get("RUNPOD_TEMPLATE_ID", "").strip()
        if not template_id:
            existing = request("GET", f"/endpoints/{update_id}")
            template_id = existing.get("templateId") or ""
        if image and template_id:
            template = patch_template(template_id, image)
            print(
                "Template:",
                json.dumps(
                    {
                        "id": template.get("id"),
                        "containerDiskInGb": template.get("containerDiskInGb"),
                        "volumeInGb": template.get("volumeInGb"),
                        "imageName": template.get("imageName"),
                    },
                    indent=2,
                ),
            )
        endpoint = patch_endpoint(update_id, volume)
        _print_endpoint(endpoint)
        return 0

    if not image:
        print("Set DOCKER_IMAGE to your pushed worker image", file=sys.stderr)
        return 1
    if not volume:
        print(
            "Warning: RUNPOD_NETWORK_VOLUME_ID is empty. "
            "The endpoint will start without MiniMax weights.",
            file=sys.stderr,
        )

    template = request("POST", "/templates", template_body(image))
    print("Template:", json.dumps(template, indent=2))
    template_id = template.get("id") or template.get("templateId")
    if not template_id:
        print("Could not read template id from response", file=sys.stderr)
        return 1

    endpoint = request("POST", "/endpoints", endpoint_body(template_id, volume or ""))
    _print_endpoint(endpoint)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
