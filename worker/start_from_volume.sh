#!/usr/bin/env bash
# Run MiniMax using ComfyUI from the image and weights already on the Network Volume.
# The GUI image is only the CUDA/ComfyUI stack (~10 GB). It must NOT download models.
set -euo pipefail

export PYTHONUNBUFFERED=1
# Fail fast instead of pulling ~56 GB from Hugging Face. Weights are on the volume.
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"
APP_ROOT="${APP_ROOT:-}"
if [[ -z "${APP_ROOT}" ]]; then
  for candidate in /runpod-volume/nsfw_prompts /workspace/nsfw_prompts; do
    if [[ -d "${candidate}/minimax_r2v" ]]; then
      APP_ROOT="${candidate}"
      break
    fi
  done
fi
APP_ROOT="${APP_ROOT:-/runpod-volume/nsfw_prompts}"
export PYTHONPATH="${APP_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
export WORKFLOW_PATH="${WORKFLOW_PATH:-${APP_ROOT}/workflows/api_template.json}"

COMFY_ROOT="${COMFY_ROOT:-/ComfyUI}"
if [[ ! -f "${COMFY_ROOT}/main.py" ]]; then
  for candidate in /ComfyUI /comfyui /runpod-volume/ComfyUI /workspace/ComfyUI; do
    if [[ -f "${candidate}/main.py" ]]; then
      COMFY_ROOT="${candidate}"
      break
    fi
  done
fi
if [[ ! -f "${COMFY_ROOT}/main.py" ]]; then
  echo "ComfyUI main.py not found at ${COMFY_ROOT}" >&2
  exit 1
fi
if [[ ! -d "${APP_ROOT}/minimax_r2v" ]]; then
  echo "Worker code not found at ${APP_ROOT}. Bootstrap the volume from this repo." >&2
  exit 1
fi

# MiniMax ships ComfyUI-Login. Without a PASSWORD file it 401s /prompt and
# logs "Please set up your password..." on every health check.
seed_comfy_login() {
  local root node dest
  local token="${COMFY_LOGIN_TOKEN:-minimax-r2v}"
  export COMFY_LOGIN_TOKEN="${token}"
  for root in "${COMFY_ROOT}" /ComfyUI /workspace/ComfyUI; do
    [[ -d "${root}" ]] || continue
    for node in "${root}/custom_nodes/ComfyUI-Login" "${root}/custom_nodes/comfyui-login"; do
      if [[ -d "${node}" ]]; then
        dest="${root}/custom_nodes/.disabled-ComfyUI-Login"
        echo "minimax-r2v: disabling ComfyUI-Login at ${node}"
        rm -rf "${dest}"
        mv "${node}" "${dest}" || rm -rf "${node}"
      fi
    done
    mkdir -p "${root}/login"
    printf '%s\nworker\n' "${token}" > "${root}/login/PASSWORD"
    touch "${root}/login/GUEST_MODE"
  done
}
seed_comfy_login

export COMFY_INPUT_DIR="${COMFY_INPUT_DIR:-${COMFY_ROOT}/input}"
mkdir -p "${COMFY_INPUT_DIR}" "${COMFY_ROOT}/output"

if [[ -f "${APP_ROOT}/worker/extra_model_paths.yaml" ]]; then
  cp "${APP_ROOT}/worker/extra_model_paths.yaml" "${COMFY_ROOT}/extra_model_paths.yaml"
fi

python -m pip install --quiet --disable-pip-version-check runpod boto3 requests

ensure_refpack() {
  local dest="${COMFY_ROOT}/custom_nodes/ComfyUI-MiniMaxRefPack"
  local ref="${REFPACK_REF:-7012734eabf6f98063d6eaf8ce1f9264ee803664}"
  if [[ -d "${dest}" ]]; then
    echo "minimax-r2v: ComfyUI-MiniMaxRefPack already present"
    return 0
  fi
  echo "minimax-r2v: cloning ComfyUI-MiniMaxRefPack ${ref}"
  git clone https://github.com/Hearmeman24/ComfyUI-MiniMaxRefPack.git "${dest}"
  git -C "${dest}" checkout "${ref}"
  if [[ -f "${dest}/requirements.txt" ]]; then
    python -m pip install --quiet --disable-pip-version-check -r "${dest}/requirements.txt"
  fi
}
ensure_refpack

if [[ "${SKIP_VOLUME_CHECK:-0}" != "1" ]]; then
  echo "minimax-r2v: checking Network Volume weights (already bootstrapped, no download)"
  python - <<'PY'
from minimax_r2v.volume import assert_weights_if_volume_present
assert_weights_if_volume_present()
PY
fi

echo "minimax-r2v: starting ComfyUI from ${COMFY_ROOT} app=${APP_ROOT}"
python "${COMFY_ROOT}/main.py" \
  --listen 127.0.0.1 \
  --port 8188 \
  --disable-auto-launch \
  --disable-metadata \
  --log-stdout &
COMFY_PID=$!
echo "${COMFY_PID}" > /tmp/comfyui.pid
sleep 2
if ! kill -0 "${COMFY_PID}" 2>/dev/null; then
  echo "minimax-r2v: ComfyUI exited during startup" >&2
  wait "${COMFY_PID}" || true
  exit 1
fi

run_airtable_drain() {
  echo "minimax-r2v: draining Airtable Todo/Queued then parking (GPU is stopped from outside)"
  set +e
  python - <<'PY'
import os
import sys

from minimax_r2v.queue import drain_airtable_queue

stats = drain_airtable_queue()
print(stats, flush=True)
# Park so RunPod does not restart the container. The launcher deletes the pod.
os.execvp("sleep", ["sleep", "infinity"])
PY
  status=$?
  set -e
  kill "${COMFY_PID}" 2>/dev/null || true
  wait "${COMFY_PID}" 2>/dev/null || true
  exit "${status}"
}

if [[ -n "${AIRTABLE_RECORD_ID:-}" || "${AIRTABLE_DRAIN:-0}" == "1" ]]; then
  run_airtable_drain
fi

echo "minimax-r2v: starting RunPod handler"
python "${APP_ROOT}/worker/handler.py" &
HANDLER_PID=$!

while true; do
  if ! kill -0 "${COMFY_PID}" 2>/dev/null; then
    echo "minimax-r2v: ComfyUI exited, stopping handler" >&2
    kill "${HANDLER_PID}" 2>/dev/null || true
    wait "${COMFY_PID}" || true
    exit 1
  fi
  if ! kill -0 "${HANDLER_PID}" 2>/dev/null; then
    set +e
    wait "${HANDLER_PID}"
    status=$?
    set -e
    kill "${COMFY_PID}" 2>/dev/null || true
    exit "${status}"
  fi
  sleep 2
done
