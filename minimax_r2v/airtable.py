"""Airtable status + attachment updates from the worker."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import requests

DEFAULT_API = "https://api.airtable.com/v0"
PENDING_STATUSES = ("Todo", "Queued")
ACTIVE_STATUSES = ("Todo", "Queued", "Running")


class AirtableClient:
    def __init__(
        self,
        token: str | None = None,
        base_id: str | None = None,
        table: str | None = None,
        status_field: str | None = None,
        output_field: str | None = None,
        error_field: str | None = None,
        job_id_field: str | None = None,
    ) -> None:
        self.token = token or os.environ.get("AIRTABLE_TOKEN", "")
        self.base_id = base_id or os.environ.get("AIRTABLE_BASE_ID", "")
        self.table = table or os.environ.get("AIRTABLE_TABLE_NAME", "Minimax")
        self.status_field = status_field or os.environ.get("AIRTABLE_STATUS_FIELD", "Status")
        self.output_field = output_field or os.environ.get("AIRTABLE_OUTPUT_FIELD", "Output")
        self.error_field = error_field or os.environ.get("AIRTABLE_ERROR_FIELD", "Errore")
        self.job_id_field = job_id_field or os.environ.get("AIRTABLE_JOB_ID_FIELD", "Job ID")

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.base_id and self.table)

    def list_records(self, formula: str | None = None) -> list[dict[str, Any]]:
        if not self.enabled:
            raise RuntimeError("Airtable is not configured")
        records: list[dict[str, Any]] = []
        offset = None
        while True:
            params: dict[str, str] = {"pageSize": "100"}
            if formula:
                params["filterByFormula"] = formula
            if offset:
                params["offset"] = offset
            url = f"{DEFAULT_API}/{self.base_id}/{quote(self.table, safe='')}"
            response = requests.get(
                url,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "User-Agent": "minimax-r2v/1.0",
                },
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            records.extend(payload.get("records") or [])
            offset = payload.get("offset")
            if not offset:
                return records

    def list_pending(self) -> list[dict[str, Any]]:
        field = self.status_field.replace("'", "\\'")
        parts = ",".join(f"{{{field}}}='{status}'" for status in PENDING_STATUSES)
        return self.list_records(f"OR({parts})")

    def get_record(self, record_id: str) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("Airtable is not configured")
        url = (
            f"{DEFAULT_API}/{self.base_id}/"
            f"{quote(self.table, safe='')}/{record_id}"
        )
        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "User-Agent": "minimax-r2v/1.0",
            },
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
            # Output is an R2 URL field, not an Airtable attachment.
            fields[self.output_field] = video_url
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
                "User-Agent": "minimax-r2v/1.0",
            },
            json={"fields": fields, "typecast": True},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
