"""Validate ComfyUI API graphs so a missing node cannot be queued."""

from __future__ import annotations

from typing import Any

# Nodes that must exist in the MiniMax H3 R2V API template (IDs may vary
# for custom graphs; class types are the source of truth).
REQUIRED_CLASS_TYPES = (
    "MiniMaxH3ReferencePack",
    "MiniMaxH3ReferenceToVideo",
    "UNETLoader",
    "VAELoader",
    "CLIPLoader",
    "LoraLoaderModelOnly",
    "SamplerCustomAdvanced",
    "VHS_VideoCombine",
)


def _is_link(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) >= 1
        and isinstance(value[0], str)
        and str(value[0]).isdigit()
    )


def dangling_links(workflow: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for node_id, node in workflow.items():
        inputs = node.get("inputs") or {}
        for key, value in inputs.items():
            if _is_link(value) and value[0] not in workflow:
                missing.append(f"{node_id}.{key} -> {value[0]}")
    return missing


def missing_class_types(workflow: dict[str, Any]) -> list[str]:
    present = {node.get("class_type") for node in workflow.values()}
    return [name for name in REQUIRED_CLASS_TYPES if name not in present]


def looks_like_minimax_r2v(workflow: dict[str, Any]) -> bool:
    types = {node.get("class_type") for node in workflow.values()}
    return "MiniMaxH3ReferencePack" in types or "MiniMaxH3ReferenceToVideo" in types


def assert_workflow_links(workflow: dict[str, Any]) -> None:
    if not isinstance(workflow, dict) or not workflow:
        raise ValueError("workflow is empty")
    broken = dangling_links(workflow)
    if broken:
        raise ValueError("workflow has links to missing nodes: " + ", ".join(broken))
    if looks_like_minimax_r2v(workflow):
        missing = missing_class_types(workflow)
        if missing:
            raise ValueError("workflow is missing required MiniMax nodes: " + ", ".join(missing))
