import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from minimax_r2v.comfy import ComfyClient
from minimax_r2v.run import run_job


class FakeComfyHandler(BaseHTTPRequestHandler):
    prompt_id = "prompt-http-1"
    mp4 = b"\x00\x00\x00\x18ftypmp42" + b"fake-mp4"

    def log_message(self, format, *args):
        return

    def _json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/system_stats":
            self._json({"system": {"comfyui": "ok"}})
            return
        if parsed.path == f"/history/{self.prompt_id}":
            self._json(
                {
                    self.prompt_id: {
                        "status": {"completed": True, "status_str": "success", "messages": []},
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
                        },
                    }
                }
            )
            return
        if parsed.path == "/view":
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(self.mp4)))
            self.end_headers()
            self.wfile.write(self.mp4)
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        prompt = body.get("prompt") or {}
        assert "185" in prompt
        self._json({"prompt_id": self.prompt_id})


def _serve():
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeComfyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host = f"127.0.0.1:{server.server_address[1]}"
    return server, host


def test_comfy_client_sends_login_token(monkeypatch):
    seen = {}

    class FakeComfyHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def do_GET(self):
            seen["auth"] = self.headers.get("Authorization")
            parsed = urlparse(self.path)
            seen["query"] = parsed.query
            data = json.dumps({"system": {"comfyui": "ok"}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            self.send_response(200)
            self.end_headers()

    monkeypatch.setenv("COMFY_LOGIN_TOKEN", "secret-token")
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeComfyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = ComfyClient(f"127.0.0.1:{server.server_address[1]}")
        client.wait_until_ready(retries=5, interval=0.01)
    finally:
        server.shutdown()
    assert seen["auth"] == "Bearer secret-token"
    assert "token=secret-token" in seen["query"]


def test_comfy_client_over_http():
    server, host = _serve()
    try:
        client = ComfyClient(host)
        client.wait_until_ready(retries=5, interval=0.01)
        prompt_id = client.queue_prompt({"185": {"class_type": "MiniMaxH3ReferencePack", "inputs": {}}})
        history = client.wait_for_prompt(prompt_id, poll_interval=0.01, timeout=5)
        videos = client.collect_videos(history)
        data = client.download_file(videos[0]["filename"])
        assert data.startswith(b"\x00\x00\x00\x18ftyp")
    finally:
        server.shutdown()


def test_run_job_against_http_comfy(monkeypatch, tmp_path):
    server, host = _serve()
    monkeypatch.setenv("COMFY_HOST", host)
    monkeypatch.setenv("COMFY_INPUT_DIR", str(tmp_path / "input"))
    monkeypatch.setenv("WORKFLOW_PATH", "workflows/api_template.json")
    monkeypatch.setenv("SKIP_MOTION_LORA", "1")
    monkeypatch.setenv("SKIP_VOLUME_CHECK", "1")
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.delenv("AIRTABLE_TOKEN", raising=False)
    monkeypatch.delenv("BUCKET_ENDPOINT_URL", raising=False)

    dest = tmp_path / "input"
    dest.mkdir(parents=True)

    def fake_download(items, destination, timeout=120):
        saved = []
        for item in items:
            name = item.filename or f"{item.kind}.bin"
            (dest / name).write_bytes(b"x")
            saved.append((item, name))
        return saved

    monkeypatch.setattr("minimax_r2v.run.download_media", fake_download)
    try:
        result = run_job(
            {
                "id": "job-http",
                "input": {
                    "prompt": "The woman from <Picture 1>",
                    "images": ["https://example.com/a.png"],
                    "duration": 8,
                },
            }
        )
    finally:
        server.shutdown()
    assert "error" not in result
    assert result["prompt_id"] == "prompt-http-1"
    assert result["videos"][0]["type"] == "base64"
