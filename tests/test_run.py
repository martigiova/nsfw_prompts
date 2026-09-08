import base64
import json

from minimax_r2v.comfy import ComfyClient
from minimax_r2v.run import run_job


class FakeResponse:
    def __init__(self, payload, status=200, content=b""):
        self._payload = payload
        self.status_code = status
        self.content = content

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def test_collects_vhs_mp4_from_gifs_key():
    client = ComfyClient()
    files = client.collect_videos(
        {
            "outputs": {
                "119": {
                    "gifs": [
                        {
                            "filename": "minimax_r2v_00001.mp4",
                            "subfolder": "",
                            "type": "output",
                            "format": "video/h264-mp4",
                        }
                    ]
                }
            }
        }
    )
    assert files[0]["filename"] == "minimax_r2v_00001.mp4"


def test_run_job_happy_path(monkeypatch, tmp_path):
    monkeypatch.setenv("COMFY_INPUT_DIR", str(tmp_path / "input"))
    monkeypatch.setenv("WORKFLOW_PATH", "workflows/api_template.json")
    monkeypatch.setenv("SKIP_MOTION_LORA", "1")
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.delenv("BUCKET_ENDPOINT_URL", raising=False)
    monkeypatch.delenv("AIRTABLE_TOKEN", raising=False)

    downloaded = []

    def fake_download(items, destination, timeout=120):
        downloaded.append([item.filename for item in items])
        (tmp_path / "input").mkdir(parents=True, exist_ok=True)
        return [(item, item.filename or f"{item.kind}.bin") for item in items]

    class FakeComfy:
        def wait_until_ready(self):
            return None

        def queue_prompt(self, workflow, client_id=None):
            assert workflow["185"]["inputs"]["direction"].startswith("Hello")
            refs = json.loads(workflow["185"]["inputs"]["references_json"])
            assert refs["references"][0]["kind"] == "image"
            return "prompt-1"

        def wait_for_prompt(self, prompt_id, poll_interval=2.0, timeout=3600):
            return {"outputs": {"119": {"gifs": [{"filename": "out.mp4", "subfolder": "", "type": "output"}]}}}

        def collect_videos(self, history):
            return ComfyClient().collect_videos(history)

        def download_file(self, filename, subfolder="", file_type="output"):
            return b"fake-mp4"

    monkeypatch.setattr("minimax_r2v.run.download_media", fake_download)
    monkeypatch.setattr("minimax_r2v.run.ComfyClient", lambda host=None: FakeComfy())

    result = run_job(
        {
            "id": "job-1",
            "input": {
                "prompt": "Hello from <Picture 1>",
                "images": ["https://example.com/a.png"],
                "duration": 8,
            },
        }
    )
    assert "error" not in result
    assert result["videos"][0]["type"] == "base64"
    assert base64.b64decode(result["videos"][0]["data"]) == b"fake-mp4"
    assert downloaded


def test_run_job_validation_error():
    result = run_job({"input": {}})
    assert result["error"] == "Missing 'prompt'"
