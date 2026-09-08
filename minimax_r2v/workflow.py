"""Patch the ComfyUI API workflow with job-specific values."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .frames import h3_frame_count
from .payload import JobRequest
from .resolution import resolution_from_aspect

DEFAULT_TEMPLATE = Path(__file__).resolve().parent.parent / "workflows" / "api_template.json"

REF_PACK_NODE = "185"
R2V_NODE = "184"
DURATION_NODE = "132"
SEED_NODE = "154"
LORA_NODE = "137"
UNET_NODE = "135"
TURBO_NODE = "158"


def load_template(path: str | Path | None = None) -> dict[str, Any]:
    template_path = Path(path or DEFAULT_TEMPLATE)
    with template_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_workflow(
    job: JobRequest,
    references: list[dict[str, Any]],
    *,
    template: dict[str, Any] | None = None,
    template_path: str | Path | None = None,
    openrouter_api_key: str = "",
    openrouter_model: str = "google/gemini-3-flash-preview",
    motion_lora_name: str | None = None,
    skip_motion_lora: bool = False,
) -> dict[str, Any]:
    if job.workflow:
        return deepcopy(job.workflow)

    workflow = deepcopy(template or load_template(template_path))
    width, height = resolution_from_aspect(job.aspect_ratio)
    length = h3_frame_count(job.duration)

    pack = workflow[REF_PACK_NODE]["inputs"]
    pack["direction"] = job.prompt
    pack["references_json"] = json.dumps({"references": references}, ensure_ascii=False)
    pack["prompt_provider"] = "openrouter" if job.auto_prompt else "none"
    pack["openrouter_api_key"] = openrouter_api_key if job.auto_prompt else ""
    pack["openrouter_model"] = openrouter_model
    pack["job_type"] = job.job_type
    pack["width"] = width
    pack["height"] = height
    pack["length_seconds"] = job.duration

    r2v = workflow[R2V_NODE]["inputs"]
    r2v["width"] = width
    r2v["height"] = height
    r2v["length"] = length

    workflow[DURATION_NODE]["inputs"]["value"] = job.duration
    workflow[SEED_NODE]["inputs"]["noise_seed"] = job.seed if job.seed else _random_seed()

    lora_name = job.motion_lora or motion_lora_name
    skip = skip_motion_lora or job.skip_motion_lora or not lora_name
    _apply_motion_lora(workflow, lora_name, skip)
    return workflow


def _apply_motion_lora(workflow: dict[str, Any], lora_name: str | None, skip: bool) -> None:
    if LORA_NODE not in workflow:
        return
    if skip or not lora_name:
        # Bypass rgthree: turbo reads the base UNET directly.
        workflow[TURBO_NODE]["inputs"]["model"] = [UNET_NODE, 0]
        workflow.pop(LORA_NODE, None)
        return
    lora = workflow[LORA_NODE]["inputs"]
    matched = False
    for key, value in list(lora.items()):
        if not key.startswith("lora_") or not isinstance(value, dict):
            continue
        if lora_name and value.get("lora") == lora_name:
            value["on"] = True
            matched = True
        elif key != "lora_7":
            value["on"] = bool(value.get("on", False))
    if not matched:
        lora["lora_1"] = {"on": True, "lora": lora_name, "strength": 1}


def _random_seed() -> int:
    import random

    return random.randint(0, 2**63 - 1)
