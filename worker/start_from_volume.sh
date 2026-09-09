#!/usr/bin/env bash
# Run the MiniMax GUI image as serverless using code + weights on the Network Volume.
# No custom Docker build: image is ls250824/run-comfyui-minimax:<date>.
set -euo pipefail

export PYTHONUNBUFFERED=1
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
  echo "ComfyUI main.py not found at ${COMFY_ROOT}" >&2
  exit 1
fi
if [[ ! -d "${APP_ROOT}/minimax_r2v" ]]; then
  echo "Worker code not found at ${APP_ROOT}. Bootstrap the volume from this repo." >&2
  exit 1
fi

export COMFY_INPUT_DIR="${COMFY_INPUT_DIR:-${COMFY_ROOT}/input}"
mkdir -p "${COMFY_INPUT_DIR}" "${COMFY_ROOT}/output"

if [[ -f "${APP_ROOT}/worker/extra_model_paths.yaml" ]]; then
  cp "${APP_ROOT}/worker/extra_model_paths.yaml" "${COMFY_ROOT}/extra_model_paths.yaml"
fi

python -m pip install --quiet --disable-pip-version-check runpod boto3 requests

if [[ "${SKIP_VOLUME_CHECK:-0}" != "1" ]]; then
  echo "minimax-r2v: checking Network Volume weights"
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
