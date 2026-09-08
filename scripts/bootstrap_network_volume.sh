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

python3 -m pip install -U "huggingface_hub[cli]" hf_xet >/dev/null

python3 - <<'PY'
import os
from pathlib import Path
from huggingface_hub import hf_hub_download

repo = os.environ.get("HF_REPO", "Comfy-Org/MiniMax-H3")
models = Path(os.environ.get("VOLUME_ROOT", "/workspace")) / "models"
files = [
    ("diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors", "diffusion_models"),
    ("text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors", "text_encoders"),
    ("vae/minimax_h3_video_vae_fp16.safetensors", "vae"),
    ("vae/minimax_h3_audio_vae_fp32.safetensors", "vae"),
    ("loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors", "loras"),
]
token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
for repo_path, dest_dir in files:
    dest = models / dest_dir / Path(repo_path).name
    if dest.exists() and dest.stat().st_size > 1_000_000:
        print(f"OK  already present: {dest}")
        continue
    print(f"DL  {repo}/{repo_path}")
    downloaded = hf_hub_download(
        repo_id=repo,
        filename=repo_path,
        token=token,
        local_dir=str(models / ".hf-tmp"),
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    Path(downloaded).replace(dest)
    print(f"    -> {dest}")
PY

ln -sfn "${MODELS}/diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors" \
  "${MODELS}/unet/minimax_h3_ref2va_pruned_int8_convrot.safetensors"
ln -sfn "${MODELS}/text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors" \
  "${MODELS}/clip/qwen3vl_32b_minimax_h3_int8_convrot.safetensors"

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
