from scripts.provision_runpod import GPU_TYPE_IDS, worker_env


def test_gpu_type_ids_match_runpod_enum():
    assert "NVIDIA GeForce RTX 4090" in GPU_TYPE_IDS
    assert "NVIDIA RTX A6000" in GPU_TYPE_IDS
    assert "NVIDIA RTX 4090" not in GPU_TYPE_IDS
    assert "NVIDIA A6000" not in GPU_TYPE_IDS


def test_worker_env_sets_comfy_input_dir(monkeypatch):
    monkeypatch.setenv("AIRTABLE_TOKEN", "tok")
    monkeypatch.setenv("AIRTABLE_BASE_ID", "appX")
    env = worker_env()
    assert env["COMFY_INPUT_DIR"] == "/ComfyUI/input"
    assert env["COMFY_ROOT"] == "/ComfyUI"
    assert env["COMFY_WAIT_TIMEOUT"] == "1650"
    assert env["AIRTABLE_TOKEN"] == "tok"
    assert env["AIRTABLE_BASE_ID"] == "appX"
    assert env["AIRTABLE_TABLE_NAME"] == "Minimax"
    assert env["APP_ROOT"] == "/runpod-volume/nsfw_prompts"
    assert env["SKIP_MOTION_LORA"] == "1"


def test_worker_env_copies_airtable_field_names(monkeypatch):
    monkeypatch.setenv("AIRTABLE_STATUS_FIELD", "Stato")
    monkeypatch.setenv("AIRTABLE_OUTPUT_FIELD", "Video")
    env = worker_env()
    assert env["AIRTABLE_STATUS_FIELD"] == "Stato"
    assert env["AIRTABLE_OUTPUT_FIELD"] == "Video"
