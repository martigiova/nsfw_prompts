#!/usr/bin/env bash
# Serverless entrypoint for the MiniMax GUI template image.
# Skips the Pod provisioning UI/downloads: weights come from the Network Volume.
set -euo pipefail

export PYTHONUNBUFFERED=1
export PYTHONPATH="${PYTHONPATH:-/app}"
export WORKFLOW_PATH="${WORKFLOW_PATH:-/app/workflows/api_template.json}"

COMFY_ROOT="${COMFY_ROOT:-/ComfyUI}"
if [[ ! -f "${COMFY_ROOT}/main.py" ]]; then
  echo "ComfyUI main.py not found at ${COMFY_ROOT}" >&2
  exit 1
fi

# MiniMaxH3ReferencePack joins references_json filenames with
# folder_paths.get_input_directory(). That is THIS process's input folder,
# not /runpod-volume/ComfyUI/input. Keep them identical.
export COMFY_INPUT_DIR="${COMFY_INPUT_DIR:-${COMFY_ROOT}/input}"
mkdir -p "${COMFY_INPUT_DIR}" "${COMFY_ROOT}/output"

if [[ -f /app/worker/extra_model_paths.yaml ]]; then
  cp /app/worker/extra_model_paths.yaml "${COMFY_ROOT}/extra_model_paths.yaml"
fi

echo "minimax-r2v: starting ComfyUI from ${COMFY_ROOT} input=${COMFY_INPUT_DIR}"
python "${COMFY_ROOT}/main.py" \
  --listen 127.0.0.1 \
  --port 8188 \
  --disable-auto-launch \
  --disable-metadata \
  --input-directory "${COMFY_INPUT_DIR}" \
  --verbose INFO \
  --log-stdout &
echo $! > /tmp/comfyui.pid

echo "minimax-r2v: starting RunPod handler"
exec python /handler.py
