from minimax_r2v.payload import apply_airtable_fields, parse_job_input
from minimax_r2v.run import run_job


def _touch_media(items, dest):
    dest.mkdir(parents=True, exist_ok=True)
    saved = []
    for item in items:
        name = item.filename or f"{item.kind}.bin"
        (dest / name).write_bytes(b"x")
        saved.append((item, name))
    return saved


AIRTABLE_FIELDS = {
    "Prompt": "The woman from <Picture 1> walks like <Video 1>",
    "Image": [
        {"url": "https://v5.airtableusercontent.com/a.png", "filename": "face.png"},
        {"url": "https://v5.airtableusercontent.com/b.png", "filename": "clothes.png"},
    ],
    "Video": [{"url": "https://v5.airtableusercontent.com/walk.mp4", "filename": "walk.mp4"}],
    "Duration": 8,
    "Aspect": "9:16",
    "Auto Prompt": False,
}


def test_hydrate_fills_prompt_images_video_without_audio():
    job, error = parse_job_input({"airtable_record_id": "rec1"})
    assert error is None
    filled = apply_airtable_fields(job, AIRTABLE_FIELDS)
    assert filled.needs_hydrate() is False
    assert filled.prompt.startswith("The woman")
    assert [item.filename for item in filled.images] == ["face.png", "clothes.png"]
    assert filled.videos[0].filename == "walk.mp4"
    assert filled.audios == []


def test_hydrate_italian_image_field():
    job, _ = parse_job_input({"airtable_record_id": "rec1"})
    filled = apply_airtable_fields(
        job,
        {
            "Prompt": "ciao",
            "Immagine": [{"url": "https://x/a.png", "filename": "a.png"}],
            "Video": [{"url": "https://x/v.mp4", "filename": "v.mp4"}],
        },
    )
    assert filled.images[0].filename == "a.png"
    assert filled.needs_hydrate() is False


def test_hydrate_optional_audio():
    job, _ = parse_job_input({"airtable_record_id": "rec1"})
    fields = dict(AIRTABLE_FIELDS)
    fields["Audio"] = [{"url": "https://v5.airtableusercontent.com/voice.wav", "filename": "voice.wav"}]
    filled = apply_airtable_fields(job, fields)
    assert filled.audios[0].filename == "voice.wav"


def test_run_job_hydrates_from_airtable(monkeypatch, tmp_path):
    monkeypatch.setenv("COMFY_INPUT_DIR", str(tmp_path / "input"))
    monkeypatch.setenv("WORKFLOW_PATH", "workflows/api_template.json")
    monkeypatch.setenv("SKIP_MOTION_LORA", "1")
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.setenv("AIRTABLE_TOKEN", "tok")
    monkeypatch.setenv("AIRTABLE_BASE_ID", "appX")
    monkeypatch.delenv("BUCKET_ENDPOINT_URL", raising=False)

    class FakeAirtable:
        enabled = True
        status_field = "Status"
        error_field = "Errore"

        def get_record(self, record_id):
            assert record_id == "rec1"
            return {"id": record_id, "fields": AIRTABLE_FIELDS}

        def mark_running(self, record_id, job_id):
            return None

        def mark_done(self, *args, **kwargs):
            return None

        def patch(self, *args, **kwargs):
            return {}

    class FakeComfy:
        def wait_until_ready(self):
            return None

        def queue_prompt(self, workflow, client_id=None):
            assert "face.png" in workflow["185"]["inputs"]["references_json"]
            assert "walk.mp4" in workflow["185"]["inputs"]["references_json"]
            return "prompt-1"

        def wait_for_prompt(self, prompt_id, poll_interval=2.0, timeout=3600):
            return {"outputs": {"119": {"gifs": [{"filename": "out.mp4", "subfolder": "", "type": "output"}]}}}

        def collect_videos(self, history):
            from minimax_r2v.comfy import ComfyClient

            return ComfyClient().collect_videos(history)

        def download_file(self, filename, subfolder="", file_type="output"):
            return b"fake-mp4"

    monkeypatch.setattr("minimax_r2v.run.AirtableClient", lambda **kwargs: FakeAirtable())
    monkeypatch.setattr(
        "minimax_r2v.run.download_media",
        lambda items, destination, timeout=120: _touch_media(items, tmp_path / "input"),
    )
    monkeypatch.setattr("minimax_r2v.run.ComfyClient", lambda host=None: FakeComfy())

    result = run_job({"id": "job-1", "input": {"airtable_record_id": "rec1"}})
    assert "error" not in result
    assert result["references"] == ["face.png", "clothes.png", "walk.mp4"]
