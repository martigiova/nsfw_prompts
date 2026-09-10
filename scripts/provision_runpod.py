#!/usr/bin/env python3
"""Create a RunPod serverless template + endpoint (requires RUNPOD_API_KEY)."""

from __future__ import annotations

import json
import os
import sys

from scripts.runpod_http import request, resolve_data_center

# MiniMax H3 weights (~56 GB) live on the Network Volume. The container only
# needs the ComfyUI image (~10 GB) plus temp outputs — not the GUI's 250 GB disk.
DEFAULT_CONTAINER_DISK_GB = 30
DEFAULT_DOCKER_IMAGE = "ls250824/run-comfyui-minimax:08092026"

# Exact enum values from POST /endpoints (wrong names are rejected).
# 1080p MiniMax R2V needs ~96 GB. Do not fall back to 24 GB 4090.
GPU_TYPE_IDS = [
    "NVIDIA RTX PRO 6000 Blackwell Server Edition",
    "NVIDIA RTX PRO 6000 Blackwell Workstation Edition",
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
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "AIRTABLE_DRAIN",
        "AIRTABLE_IDLE_SECONDS",
        "AIRTABLE_POLL_SECONDS",
        "VIDEO_MEGAPIXELS",
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
        "HF_HUB_OFFLINE": os.environ.get("HF_HUB_OFFLINE", "1"),
        "TRANSFORMERS_OFFLINE": os.environ.get("TRANSFORMERS_OFFLINE", "1"),
        "AIRTABLE_DRAIN": os.environ.get("AIRTABLE_DRAIN", "1"),
        "AIRTABLE_IDLE_SECONDS": os.environ.get("AIRTABLE_IDLE_SECONDS", "30"),
        # MiniMax /start.sh starts code-server when this is set. Harmless if we
        # replace the entrypoint; required if the GUI script still runs.
        "PASSWORD": os.environ.get("PASSWORD", "minimax-r2v"),
    }
    for key in keys:
        value = os.environ.get(key)
        if value:
            env[key] = value
    return env


VOLUME_ENTRYPOINT = r"""set -euo pipefail
echo "minimax-r2v: Network Volume job — weights stay on the volume, no HF download"
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
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"
if command -v git >/dev/null 2>&1 && [ -d "$ROOT/.git" ]; then
  git -C "$ROOT" fetch --depth 1 origin cursor/minimax-runpod-serverless-9e74 || true
  git -C "$ROOT" reset --hard FETCH_HEAD || true
fi
exec /bin/bash "$ROOT/worker/start_from_volume.sh"
"""


V1_TEMPLATE_PATCH_KEYS = (
    "name",
    "imageName",
    "containerDiskInGb",
    "volumeInGb",
    "volumeMountPath",
    "dockerEntrypoint",
    "dockerStartCmd",
    "env",
    "readme",
)


def template_body(image: str) -> dict:
    return {
        "name": os.environ.get("RUNPOD_TEMPLATE_NAME", "minimax-h3-r2v-worker"),
        "imageName": image,
        "isServerless": True,
        "containerDiskInGb": int(os.environ.get("CONTAINER_DISK_GB", str(DEFAULT_CONTAINER_DISK_GB))),
        "volumeInGb": int(os.environ.get("TEMPLATE_VOLUME_GB", "0")),
        "volumeMountPath": "/runpod-volume",
        # Entrypoint + startCmd (not []) so the MiniMax GUI image CMD is not appended.
        "dockerEntrypoint": ["/bin/bash", "-lc"],
        "dockerStartCmd": [VOLUME_ENTRYPOINT],
        "startJupyter": False,
        "startSsh": False,
        "ports": [],
        "env": worker_env(),
    }


def v1_template_payload(image: str, *, patch: bool) -> dict:
    body = template_body(image)
    if patch:
        return {key: body[key] for key in V1_TEMPLATE_PATCH_KEYS if key in body}
    return {key: value for key, value in body.items() if key not in {"startJupyter", "startSsh"}}


WORKER_CMD = (
    "set -euo pipefail; "
    "for d in /runpod-volume/nsfw_prompts /workspace/nsfw_prompts; do "
    "  if [ -d \"$d/minimax_r2v\" ]; then "
    "    if command -v git >/dev/null 2>&1 && [ -d \"$d/.git\" ]; then "
    "      git -C \"$d\" fetch --depth 1 origin cursor/minimax-runpod-serverless-9e74 || true; "
    "      git -C \"$d\" reset --hard FETCH_HEAD || true; "
    "    fi; "
    "    exec /bin/bash \"$d/worker/start_from_volume.sh\"; "
    "  fi; "
    "done; "
    "echo nsfw_prompts not found on the Network Volume; ls -la /runpod-volume /workspace || true; exit 1"
)


def worker_start_args() -> str:
    """Replace the MiniMax image CMD (`/start.sh`), which ignores extra args.

    v2 `args` is a string. A JSON object with `entrypoint` + `cmd` is the
    format the RunPod console uses to override both ENTRYPOINT and CMD.
    A plain `/bin/bash -lc ...` string is appended to `/start.sh` instead.
    """
    return json.dumps({"entrypoint": ["/bin/bash", "-lc"], "cmd": [WORKER_CMD]})


def _v2_request(method: str, path: str, payload: dict) -> dict:
    import urllib.request

    api_key = os.environ.get("RUNPOD_API_KEY")
    req = urllib.request.Request(
        f"https://api.runpod.io{path}",
        data=json.dumps(payload).encode(),
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "minimax-r2v/1.0",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def disable_jupyter_v2(template_id: str) -> dict:
    """REST v1 cannot set startJupyter; v2 can. Default is true and starts the MiniMax GUI."""
    return _v2_request(
        "PATCH",
        f"/v2/templates/{template_id}",
        {"startJupyter": False, "startSsh": False, "serverless": True},
    )


def set_worker_cmd_v2(endpoint_id: str) -> dict:
    """Replace the MiniMax image CMD (/start.sh GUI) with the volume handler.

    v2 serverless only accepts `args` as a string; it does not honor template
    dockerEntrypoint. A plain bash string is passed *to* `/start.sh` and
    ignored. JSON `{entrypoint, cmd}` is the console override format.
    """
    env = worker_env()
    return _v2_request(
        "PATCH",
        f"/v2/serverless/{endpoint_id}",
        {
            "args": worker_start_args(),
            "disk": int(os.environ.get("CONTAINER_DISK_GB", str(DEFAULT_CONTAINER_DISK_GB))),
            "env": env,
        },
    )


def patch_template(template_id: str, image: str) -> dict:
    """Resize container disk / env on the live serverless template."""
    updated = request("PATCH", f"/templates/{template_id}", v1_template_payload(image, patch=True))
    try:
        disable_jupyter_v2(template_id)
    except Exception as exc:
        print(f"Warning: could not disable Jupyter via v2: {exc}", file=sys.stderr)
    return updated


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
        try:
            set_worker_cmd_v2(update_id)
        except Exception as exc:
            print(f"Warning: could not set v2 worker args: {exc}", file=sys.stderr)
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

    template = request("POST", "/templates", v1_template_payload(image, patch=False))
    print("Template:", json.dumps(template, indent=2))
    template_id = template.get("id") or template.get("templateId")
    if not template_id:
        print("Could not read template id from response", file=sys.stderr)
        return 1
    try:
        disable_jupyter_v2(template_id)
    except Exception as exc:
        print(f"Warning: could not disable Jupyter via v2: {exc}", file=sys.stderr)

    endpoint = request("POST", "/endpoints", endpoint_body(template_id, volume or ""))
    endpoint_id = _print_endpoint(endpoint)
    if endpoint_id:
        try:
            set_worker_cmd_v2(endpoint_id)
        except Exception as exc:
            print(f"Warning: could not set v2 worker args: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
