#!/usr/bin/env bash
# Point the GUI ComfyUI on a Pod at the canonical network-volume model tree
# so the pod and the serverless endpoint share the same weights.
set -euo pipefail

VOLUME_ROOT="${VOLUME_ROOT:-/workspace}"
MODELS="${VOLUME_ROOT}/models"

COMFY_ROOT=""
for candidate in \
  "${VOLUME_ROOT}/ComfyUI" \
  "${VOLUME_ROOT}/runpod-slim/ComfyUI" \
  /comfyui
do
  if [[ -d "${candidate}/models" ]]; then
    COMFY_ROOT="${candidate}"
    break
  fi
done

if [[ -z "${COMFY_ROOT}" ]]; then
  echo "Could not find a ComfyUI models directory under ${VOLUME_ROOT}"
  exit 1
fi

echo "ComfyUI: ${COMFY_ROOT}"
echo "Volume models: ${MODELS}"

link_dir() {
  local name="$1"
  mkdir -p "${MODELS}/${name}" "${COMFY_ROOT}/models/${name}"
  # Copy any existing pod files into the volume tree first
  if [[ -d "${COMFY_ROOT}/models/${name}" ]]; then
    find "${COMFY_ROOT}/models/${name}" -maxdepth 1 -type f | while read -r file; do
      base="$(basename "${file}")"
      if [[ ! -e "${MODELS}/${name}/${base}" ]]; then
        echo "MOVE ${file} -> ${MODELS}/${name}/${base}"
        mv "${file}" "${MODELS}/${name}/${base}"
      fi
    done
  fi
  rm -rf "${COMFY_ROOT}/models/${name}"
  ln -sfn "${MODELS}/${name}" "${COMFY_ROOT}/models/${name}"
  echo "LINK ${COMFY_ROOT}/models/${name} -> ${MODELS}/${name}"
}

for folder in diffusion_models unet text_encoders clip vae loras vae_approx; do
  link_dir "${folder}"
done

echo "Restart ComfyUI (or the pod) so it picks up the new folders."
