"""MiniMax H3 Reference-to-Video API worker for RunPod Serverless."""

from .frames import h3_frame_count
from .payload import JobRequest, apply_airtable_fields, parse_job_input
from .resolution import resolution_from_aspect
from .workflow import build_workflow

__all__ = [
    "JobRequest",
    "apply_airtable_fields",
    "build_workflow",
    "h3_frame_count",
    "parse_job_input",
    "resolution_from_aspect",
]
