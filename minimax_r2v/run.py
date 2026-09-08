"""Run a MiniMax R2V job against ComfyUI (used by the RunPod handler)."""

from __future__ import annotations

import os
import traceback
from pathlib import Path

from .airtable import AirtableClient
from .comfy import ComfyClient
from .graph import assert_workflow_links
from .loras import lora_search_dirs
from .media import download_media
from .payload import JobRequest, apply_airtable_fields, parse_job_input, references_manifest
from .storage import s3_configured, upload_file
from .volume import assert_weights_if_volume_present
from .workflow import build_workflow


def _airtable_for(job: JobRequest) -> AirtableClient | None:
    if not job.airtable:
        return None
    client = AirtableClient(base_id=job.airtable.base_id, table=job.airtable.table)
    return client if client.enabled else None


def run_job(event: dict) -> dict:
    job_id = event.get("id") or "local"
    job, error = parse_job_input(event.get("input"))
    if error:
        return {"error": error}

    comfy_host = os.environ.get("COMFY_HOST", "127.0.0.1:8188")
    input_dir = Path(os.environ.get("COMFY_INPUT_DIR", "/comfyui/input"))
    workflow_path = os.environ.get("WORKFLOW_PATH", "/app/workflows/api_template.json")
    refresh_worker = os.environ.get("REFRESH_WORKER", "false").lower() == "true"

    airtable = _airtable_for(job)
    record_id = job.airtable.record_id if job.airtable else None
    try:
        if job.needs_hydrate():
            if not airtable or not record_id:
                return {"error": "Airtable record id was sent but AIRTABLE_TOKEN/BASE_ID are missing"}
            record = airtable.get_record(record_id)
            job = apply_airtable_fields(job, record.get("fields") or {})
            if not job.prompt.strip():
                return {"error": "Airtable record is missing Prompt"}
            if not job.images and not job.videos:
                return {"error": "Airtable record needs at least one Image or Video attachment"}
            if job.duration <= 0 or job.duration > 15:
                return {"error": "duration must be between 0 and 15 seconds"}

        if airtable and record_id:
            airtable.mark_running(record_id, job_id)
            if not s3_configured():
                raise RuntimeError(
                    "S3/R2 is required to attach MiniMax mp4s to Airtable. "
                    "Set BUCKET_ENDPOINT_URL, BUCKET_NAME, BUCKET_ACCESS_KEY_ID, "
                    "BUCKET_SECRET_ACCESS_KEY and BUCKET_PUBLIC_URL_PREFIX."
                )

        assert_weights_if_volume_present()

        saved: list = []
        if not job.workflow:
            saved = download_media(job.all_media(), input_dir)
            missing = [name for _, name in saved if not (input_dir / name).is_file()]
            if missing:
                raise RuntimeError(
                    "reference file(s) not found in the ComfyUI input directory: "
                    + ", ".join(missing)
                )
            references = references_manifest(saved)
            workflow = build_workflow(
                job,
                references,
                template_path=workflow_path,
                openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
                openrouter_model=os.environ.get(
                    "OPENROUTER_MODEL", "google/gemini-3-flash-preview"
                ),
                motion_lora_name=os.environ.get("MOTION_LORA_NAME"),
                skip_motion_lora=os.environ.get("SKIP_MOTION_LORA", "0") == "1",
                lora_search_dirs=lora_search_dirs(),
            )
        else:
            workflow = job.workflow

        assert_workflow_links(workflow)
        comfy = ComfyClient(comfy_host)
        comfy.wait_until_ready()
        prompt_id = comfy.queue_prompt(workflow)
        wait_s = int(os.environ.get("COMFY_WAIT_TIMEOUT", "1650"))
        history = comfy.wait_for_prompt(prompt_id, timeout=wait_s)
        videos = comfy.collect_videos(history)
        if not videos:
            raise RuntimeError("ComfyUI finished but produced no video output")

        outputs = []
        primary_url = None
        primary_name = videos[0]["filename"]
        tmp_dir = Path(os.environ.get("TMPDIR", "/tmp"))
        for item in videos:
            data = comfy.download_file(item["filename"], item["subfolder"], item["type"])
            local_path = tmp_dir / item["filename"]
            local_path.write_bytes(data)
            entry = {"filename": item["filename"]}
            if s3_configured():
                key = f"minimax-r2v/{job_id}/{item['filename']}"
                url = upload_file(local_path, key)
                entry["type"] = "s3_url"
                entry["data"] = url
                primary_url = primary_url or url
                primary_name = item["filename"]
            else:
                import base64

                entry["type"] = "base64"
                entry["data"] = base64.b64encode(data).decode("ascii")
            outputs.append(entry)

        if airtable and record_id:
            if not primary_url:
                raise RuntimeError(
                    "Video generated but S3/R2 did not return a public URL"
                )
            airtable.mark_done(record_id, primary_url, primary_name)

        result = {
            "prompt_id": prompt_id,
            "videos": outputs,
            "references": [name for _, name in saved],
        }
        if refresh_worker:
            result["refresh_worker"] = True
        return result
    except Exception as exc:
        message = f"{exc}"
        print(traceback.format_exc())
        if airtable and record_id:
            try:
                airtable.mark_error(record_id, message)
            except Exception as airtable_exc:
                print(f"Failed to update Airtable: {airtable_exc}")
        return {"error": message}
