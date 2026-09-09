"""Talk to a local ComfyUI instance (queue prompt, wait, collect videos)."""

from __future__ import annotations

import os
import time
import uuid
from typing import Any

import requests

DEFAULT_HOST = "127.0.0.1:8188"
VIDEO_KEYS = ("gifs", "videos", "video", "images", "animated")


def _login_token() -> str:
    return os.environ.get("COMFY_LOGIN_TOKEN", "minimax-r2v")


class ComfyClient:
    def __init__(self, host: str = DEFAULT_HOST, timeout: int = 30) -> None:
        self.base = f"http://{host}"
        self.timeout = timeout
        self.session = requests.Session()
        token = _login_token()
        # MiniMax image ships ComfyUI-Login; Bearer + ?token= unlock /prompt.
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self._token = token

    def _get(self, path: str, **kwargs: Any) -> requests.Response:
        params = dict(kwargs.pop("params", None) or {})
        params.setdefault("token", self._token)
        return self.session.get(f"{self.base}{path}", params=params, **kwargs)

    def _post(self, path: str, **kwargs: Any) -> requests.Response:
        params = dict(kwargs.pop("params", None) or {})
        params.setdefault("token", self._token)
        return self.session.post(f"{self.base}{path}", params=params, **kwargs)

    def wait_until_ready(self, retries: int = 600, interval: float = 1.0) -> None:
        last_error = None
        for _ in range(retries):
            try:
                response = self._get("/system_stats", timeout=5)
                if response.status_code == 200:
                    return
                last_error = f"status {response.status_code}"
            except requests.RequestException as exc:
                last_error = str(exc)
            time.sleep(interval)
        raise RuntimeError(f"ComfyUI did not become ready: {last_error}")

    def queue_prompt(self, workflow: dict[str, Any], client_id: str | None = None) -> str:
        client_id = client_id or str(uuid.uuid4())
        payload = {"prompt": workflow, "client_id": client_id}
        response = self._post(
            "/prompt",
            json=payload,
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            detail = (response.text or "")[:2000]
            raise RuntimeError(f"ComfyUI /prompt {response.status_code}: {detail}")
        data = response.json()
        if "error" in data:
            raise RuntimeError(f"ComfyUI rejected the prompt: {data['error']}")
        node_errors = data.get("node_errors") or {}
        if node_errors:
            raise RuntimeError(f"ComfyUI node_errors: {node_errors}")
        prompt_id = data.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI did not return prompt_id: {data}")
        return prompt_id

    def wait_for_prompt(self, prompt_id: str, poll_interval: float = 2.0, timeout: int = 3600) -> dict[str, Any]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            history = self.get_history(prompt_id)
            if prompt_id in history:
                entry = history[prompt_id]
                status = entry.get("status") or {}
                messages = status.get("messages") or []
                if status.get("status_str") == "error":
                    raise RuntimeError(f"ComfyUI execution failed: {messages}")
                for msg in messages:
                    if isinstance(msg, (list, tuple)) and msg and msg[0] == "execution_error":
                        raise RuntimeError(f"ComfyUI execution failed: {msg}")
                if entry.get("outputs") or status.get("completed"):
                    return entry
            time.sleep(poll_interval)
        raise TimeoutError(f"Timed out waiting for prompt {prompt_id}")

    def get_history(self, prompt_id: str) -> dict[str, Any]:
        response = self._get(f"/history/{prompt_id}", timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def collect_videos(self, history_entry: dict[str, Any]) -> list[dict[str, Any]]:
        outputs = history_entry.get("outputs") or {}
        files: list[dict[str, Any]] = []
        for node_id, node_output in outputs.items():
            for key in VIDEO_KEYS:
                for item in node_output.get(key) or []:
                    filename = item.get("filename")
                    if not filename:
                        continue
                    if item.get("type") == "temp":
                        continue
                    files.append(
                        {
                            "node_id": node_id,
                            "filename": filename,
                            "subfolder": item.get("subfolder") or "",
                            "type": item.get("type") or "output",
                            "format": item.get("format"),
                        }
                    )
        return files

    def download_file(self, filename: str, subfolder: str = "", file_type: str = "output") -> bytes:
        params = {"filename": filename, "subfolder": subfolder, "type": file_type}
        response = self._get("/view", params=params, timeout=120)
        response.raise_for_status()
        return response.content
