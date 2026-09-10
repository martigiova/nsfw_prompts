"""Drain Airtable Todo/Queued records, then park the container (GPU is stopped from outside)."""

from __future__ import annotations

import os
import time

from .airtable import AirtableClient
from .run import run_job


def drain_airtable_queue() -> dict[str, int]:
    """Process pending MiniMax rows. GPU stays on only while there is work.

    After the queue stays empty for AIRTABLE_IDLE_SECONDS, return so the
    wrapper can `sleep infinity` until the launcher deletes the pod.
    """
    client = AirtableClient()
    if not client.enabled:
        raise RuntimeError("Airtable is not configured")
    pod_id = os.environ.get("RUNPOD_POD_ID") or os.environ.get("RUNPOD_JOB_ID") or "pod"
    first = os.environ.get("AIRTABLE_RECORD_ID", "").strip()
    idle_s = int(os.environ.get("AIRTABLE_IDLE_SECONDS", "30"))
    interval = int(os.environ.get("AIRTABLE_POLL_SECONDS", "10"))
    seen: set[str] = set()
    done = 0
    errors = 0

    def process(record_id: str) -> None:
        nonlocal done, errors
        if record_id in seen:
            return
        seen.add(record_id)
        job_id = f"{pod_id}-{record_id}"
        print(f"minimax-r2v: queue {record_id} as {job_id}", flush=True)
        result = run_job({"id": job_id, "input": {"airtable_record_id": record_id}})
        if result.get("error"):
            print(f"minimax-r2v: queue error {record_id}: {result.get('error')}", flush=True)
            errors += 1
        else:
            done += 1

    if first:
        process(first)

    empty_since: float | None = None
    while True:
        pending = [item["id"] for item in client.list_pending() if item.get("id") not in seen]
        if pending:
            empty_since = None
            for record_id in pending:
                process(record_id)
            continue
        now = time.time()
        if empty_since is None:
            empty_since = now
        waited = now - empty_since
        if waited >= idle_s:
            print(
                f"minimax-r2v: queue empty for {idle_s}s "
                f"(done={done} errors={errors}); parking until the pod is deleted",
                flush=True,
            )
            return {"done": done, "errors": errors}
        time.sleep(interval)
