"""Airtable status + attachment updates from the worker."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import requests

DEFAULT_API = "https://api.airtable.com/v0"


class AirtableClient:
    def __init__(
        self,
        token: str | None = None,
        base_id: str | None = None,
        table: str | None = None,
        status_field: str = "Status",
        output_field: str = "Output",
        error_field: str = "Errore",
        job_id_field: str = "Job ID",
    ) -> None:
        self.token = token or os.environ.get("AIRTABLE_TOKEN", "")
        self.base_id = base_id or os.environ.get("AIRTABLE_BASE_ID", "")
        self.table = table or os.environ.get("AIRTABLE_TABLE_NAME", "Generazioni")
        self.status_field = status_field or os.environ.get("AIRTABLE_STATUS_FIELD", "Status")
        self.output_field = output_field or os.environ.get("AIRTABLE_OUTPUT_FIELD", "Output")
        self.error_field = error_field or os.environ.get("AIRTABLE_ERROR_FIELD", "Errore")
        self.job_id_field = job_id_field or os.environ.get("AIRTABLE_JOB_ID_FIELD", "Job ID")

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.base_id and self.table)

    def get_record(self, record_id: str) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("Airtable is not configured")
        url = (
            f"{DEFAULT_API}/{self.base_id}/"
            f"{quote(self.table, safe='')}/{record_id}"
        )
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def mark_running(self, record_id: str, job_id: str) -> None:
        self.patch(
            record_id,
            {
                self.status_field: "Running",
                self.job_id_field: job_id,
            },
        )

    def mark_done(self, record_id: str, video_url: str, filename: str = "output.mp4") -> None:
        fields: dict[str, Any] = {self.status_field: "Done"}
        if video_url:
            fields[self.output_field] = [{"url": video_url, "filename": filename}]
        self.patch(record_id, fields)

    def mark_error(self, record_id: str, message: str) -> None:
        self.patch(
            record_id,
            {
                self.status_field: "Error",
                self.error_field: message[:10000],
            },
        )

    def patch(self, record_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("Airtable is not configured")
        url = (
            f"{DEFAULT_API}/{self.base_id}/"
            f"{quote(self.table, safe='')}/{record_id}"
        )
        response = requests.patch(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            json={"fields": fields, "typecast": True},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
