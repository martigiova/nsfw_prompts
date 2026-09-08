#!/usr/bin/env bash
# One-shot on a MiniMax GUI pod with the Network Volume mounted at /workspace.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export VOLUME_ROOT="${VOLUME_ROOT:-/workspace}"

bash "${ROOT}/scripts/bootstrap_network_volume.sh"
if [[ -d "${VOLUME_ROOT}/ComfyUI/models" ]] || [[ -d "${VOLUME_ROOT}/runpod-slim/ComfyUI/models" ]]; then
  bash "${ROOT}/scripts/link_pod_models.sh" || true
fi

python3 "${ROOT}/scripts/validate_volume.py"
echo
echo "Volume ready. Next:"
echo "  1. Stop this pod (keep the volume)."
echo "  2. Build/push worker/Dockerfile.template"
echo "  3. Create the serverless endpoint attached to this volume."
echo "  4. Paste airtable/submit_job.js into an Airtable automation (Status=Queued)."
