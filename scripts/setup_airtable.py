#!/usr/bin/env python3
"""Create/update the Airtable Minimax table fields used by the worker."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("AIRTABLE_BASE_ID", "")
TOKEN = os.environ.get("AIRTABLE_TOKEN", "")
TABLE_NAME = os.environ.get("AIRTABLE_TABLE_NAME", "Minimax")
META = f"https://api.airtable.com/v0/meta/bases/{BASE}"

FIELDS = (
    ("Prompt", {"type": "multilineText"}),
    ("Image", {"type": "multipleAttachments"}),
    ("Video", {"type": "multipleAttachments"}),
    ("Audio", {"type": "multipleAttachments"}),
    ("Duration", {"type": "number", "options": {"precision": 1}}),
    ("Aspect", {"type": "singleLineText"}),
    ("Output", {"type": "url"}),
    ("Errore", {"type": "multilineText"}),
    ("Job ID", {"type": "singleLineText"}),
)

STATUS_CHOICES = ("Todo", "Queued", "Running", "Done", "Error")
DELETE_IF_UNUSED = {"Attachments", "Notes"}


def req(method: str, path: str, payload: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode()
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "User-Agent": "minimax-r2v/1.0",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{META}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Airtable {exc.code} {method} {path}: {body}") from exc


def main() -> int:
    if not BASE or not TOKEN:
        print("Set AIRTABLE_TOKEN and AIRTABLE_BASE_ID", file=sys.stderr)
        return 1
    tables = req("GET", "/tables")["tables"]
    table = next((item for item in tables if item["name"] == TABLE_NAME), None)
    if not table:
        print(f"Table {TABLE_NAME!r} not found", file=sys.stderr)
        return 1
    table_id = table["id"]
    existing = {field["name"]: field for field in table["fields"]}
    for name, spec in FIELDS:
        if name in existing:
            print(f"OK   field {name}")
            continue
        created = req("POST", f"/tables/{table_id}/fields", {"name": name, **spec})
        print(f"ADD  {name} {created.get('id')}")
        existing[name] = created

    status = existing.get("Status")
    if status and status.get("type") == "singleSelect":
        print(
            "OK   Status (Queued/Running/Done/Error are added on first PATCH via typecast)"
        )

    for name in DELETE_IF_UNUSED:
        field = existing.get(name)
        if not field:
            continue
        try:
            req("DELETE", f"/tables/{table_id}/fields/{field['id']}")
            print(f"DEL  {name}")
        except SystemExit as exc:
            print(f"SKIP delete {name}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
