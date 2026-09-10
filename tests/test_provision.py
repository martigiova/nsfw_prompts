from scripts.provision_runpod import GPU_TYPE_IDS, patch_endpoint, worker_env
from scripts.run_gpu_pod_job import pod_body


def test_gpu_type_ids_match_runpod_enum():
    assert GPU_TYPE_IDS[0] == "NVIDIA RTX PRO 6000 Blackwell Server Edition"
    assert "NVIDIA GeForce RTX 4090" in GPU_TYPE_IDS
    assert "NVIDIA RTX A6000" in GPU_TYPE_IDS
    assert "NVIDIA A40" in GPU_TYPE_IDS
    assert "NVIDIA GeForce RTX 5090" in GPU_TYPE_IDS
    assert "NVIDIA RTX 4090" not in GPU_TYPE_IDS
    assert "NVIDIA A6000" not in GPU_TYPE_IDS


def test_patch_endpoint_reattaches_volume(monkeypatch):
    seen = {}

    def fake_request(method, path, payload=None):
        seen["method"] = method
        seen["path"] = path
        seen["payload"] = payload
        return {"id": "ep1"}

    monkeypatch.setenv("RUNPOD_API_KEY", "k")
    monkeypatch.setattr("scripts.provision_runpod.request", fake_request)
    monkeypatch.setattr("scripts.provision_runpod.resolve_data_center", lambda volume_id: "US-IL-1")
    out = patch_endpoint("ep1", "vol_new")
    assert out["id"] == "ep1"
    assert seen["method"] == "PATCH"
    assert seen["path"] == "/endpoints/ep1"
    assert seen["payload"]["networkVolumeId"] == "vol_new"
    assert seen["payload"]["dataCenterIds"] == ["US-IL-1"]
    assert seen["payload"]["gpuTypeIds"][0] == "NVIDIA RTX PRO 6000 Blackwell Server Edition"


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
    assert env["HF_HUB_OFFLINE"] == "1"
    assert env["TRANSFORMERS_OFFLINE"] == "1"
    assert env["AIRTABLE_DRAIN"] == "1"


def test_worker_env_copies_airtable_field_names(monkeypatch):
    monkeypatch.setenv("AIRTABLE_STATUS_FIELD", "Stato")
    monkeypatch.setenv("AIRTABLE_OUTPUT_FIELD", "Video")
    env = worker_env()
    assert env["AIRTABLE_STATUS_FIELD"] == "Stato"
    assert env["AIRTABLE_OUTPUT_FIELD"] == "Video"


def test_gpu_pod_job_overrides_minimax_start(monkeypatch):
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
    monkeypatch.delenv("RUNPOD_DATA_CENTER_ID", raising=False)
    monkeypatch.setenv("RUNPOD_NETWORK_VOLUME_ID", "vol_123")
    monkeypatch.setenv("AIRTABLE_TOKEN", "tok")
    monkeypatch.setenv("AIRTABLE_BASE_ID", "appX")
    body = pod_body("recABC")
    assert body["dockerEntrypoint"] == ["/bin/bash", "-lc"]
    assert "start_from_volume.sh" in body["dockerStartCmd"][0]
    assert "/start.sh" not in body["dockerStartCmd"][0]
    assert body["volumeMountPath"] == "/runpod-volume"
    assert body["env"]["AIRTABLE_RECORD_ID"] == "recABC"
    assert body["env"]["AIRTABLE_DRAIN"] == "1"
    assert body["gpuTypeIds"][0] == "NVIDIA RTX PRO 6000 Blackwell Server Edition"
    assert body["containerDiskInGb"] == 30
    assert body["env"]["HF_HUB_OFFLINE"] == "1"


def test_gpu_pod_queue_drains_without_single_record(monkeypatch):
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
    monkeypatch.delenv("RUNPOD_DATA_CENTER_ID", raising=False)
    monkeypatch.setenv("RUNPOD_NETWORK_VOLUME_ID", "vol_123")
    monkeypatch.setenv("AIRTABLE_TOKEN", "tok")
    monkeypatch.setenv("AIRTABLE_BASE_ID", "appX")
    body = pod_body(None)
    assert "AIRTABLE_RECORD_ID" not in body["env"]
    assert body["env"]["AIRTABLE_DRAIN"] == "1"
