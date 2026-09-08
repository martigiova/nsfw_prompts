#!/usr/bin/env bash
# Populate a RunPod Network Volume with MiniMax H3 R2V weights.
# Run this ONCE on a GPU Pod that has the volume mounted at /workspace
# (the same volume is later attached to the serverless endpoint as /runpod-volume).
set -euo pipefail

VOLUME_ROOT="${VOLUME_ROOT:-/workspace}"
MODELS="${VOLUME_ROOT}/models"
HF_REPO="${HF_REPO:-Comfy-Org/MiniMax-H3}"
export VOLUME_ROOT HF_REPO

echo "== MiniMax H3 volume bootstrap =="
echo "VOLUME_ROOT=${VOLUME_ROOT}"
mkdir -p \
  "${MODELS}/diffusion_models" \
  "${MODELS}/unet" \
  "${MODELS}/text_encoders" \
  "${MODELS}/clip" \
  "${MODELS}/vae" \
  "${MODELS}/loras" \
  "${MODELS}/vae_approx"

python3 -m pip install -U "huggingface_hub[cli]" >/dev/null

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
python3 -m minimax_r2v download-weights

copy_if_found() {
  local name="$1"
  local dest_dir="$2"
  local dest="${dest_dir}/${name}"
  [[ -e "${dest}" ]] && return
  local found
  found="$(find "${VOLUME_ROOT}" -name "${name}" -type f 2>/dev/null | head -n 1 || true)"
  if [[ -n "${found}" ]]; then
    echo "LINK ${found} -> ${dest}"
    ln -sfn "${found}" "${dest}"
  fi
}

copy_if_found "hmmotion_minimax-h3_epoch40.safetensors" "${MODELS}/loras"
copy_if_found "HMCumshot_v1_e120.safetensors" "${MODELS}/loras"
copy_if_found "HMNSFW_AIO_V2.safetensors" "${MODELS}/loras"
copy_if_found "HMBreasts_085e0750_e40.safetensors" "${MODELS}/loras"
copy_if_found "taeh3.safetensors" "${MODELS}/vae_approx"

rm -rf "${MODELS}/.hf-tmp"

echo
echo "== Volume layout =="
du -sh "${MODELS}"/* 2>/dev/null || true
echo
echo "Checklist:"
echo "  [ ] ${MODELS}/diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors   (~21 GB)"
echo "  [ ] ${MODELS}/text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors       (~27 GB)"
echo "  [ ] ${MODELS}/vae/minimax_h3_video_vae_fp16.safetensors                         (~5 GB)"
echo "  [ ] ${MODELS}/vae/minimax_h3_audio_vae_fp32.safetensors                        (~0.6 GB)"
echo "  [ ] ${MODELS}/loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors (~2 GB)"
echo "  [ ] ${MODELS}/loras/hmmotion_minimax-h3_epoch40.safetensors                     (dal pod GUI)"
echo
echo "On serverless this tree is visible at /runpod-volume/models"
echo "Done."
