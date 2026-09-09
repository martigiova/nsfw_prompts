from pathlib import Path

from scripts.bootstrap_via_runpod import (
    BOOTSTRAP_SCRIPT,
    interpret_status,
    pod_body,
    start_command,
    start_entrypoint,
)
from scripts.deploy import check
from scripts.provision_runpod import endpoint_body, template_body


def test_check_reports_missing_groups(monkeypatch, capsys):
    for key in (
        "RUNPOD_API_KEY",
        "RUNPOD_NETWORK_VOLUME_ID",
        "DOCKER_IMAGE",
        "AIRTABLE_TOKEN",
        "AIRTABLE_BASE_ID",
        "BUCKET_ENDPOINT_URL",
        "BUCKET_ACCESS_KEY_ID",
        "BUCKET_SECRET_ACCESS_KEY",
        "BUCKET_NAME",
        "BUCKET_PUBLIC_URL_PREFIX",
    ):
        monkeypatch.delenv(key, raising=False)
    assert check() == 1
    out = capsys.readouterr().out
    assert "MISSING volume bootstrap" in out
    assert "MISSING serverless endpoint" in out
    assert "MISSING Airtable" in out
    assert "MISSING S3/R2" in out


def test_bootstrap_pod_is_cpu_with_volume(monkeypatch):
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
    monkeypatch.delenv("RUNPOD_DATA_CENTER_ID", raising=False)
    monkeypatch.setenv("RUNPOD_NETWORK_VOLUME_ID", "vol_123")
    monkeypatch.setenv("GIT_REF", "cursor/minimax-runpod-serverless-9e74")
    body = pod_body()
    assert body["imageName"] == "runpod/base:1.1.0-ubuntu2204"
    assert body["computeType"] == "CPU"
    assert body["vcpuCount"] == 8
    assert body["networkVolumeId"] == "vol_123"
    assert body["volumeMountPath"] == "/workspace"
    assert body["dockerEntrypoint"] == start_entrypoint()
    assert body["dockerStartCmd"] == start_command()
    script = body["dockerStartCmd"][0]
    assert "scripts/on_pod.sh" in script
    assert "/workspace/nsfw_prompts" in script
    assert "validate_volume.py" in script
    assert "write_status error" in script
    assert body["env"]["GIT_REF"] == "cursor/minimax-runpod-serverless-9e74"
    assert "dataCenterIds" not in body


def test_bootstrap_pins_volume_datacenter(monkeypatch):
    monkeypatch.setenv("RUNPOD_NETWORK_VOLUME_ID", "vol_123")
    monkeypatch.setenv("RUNPOD_API_KEY", "k")
    monkeypatch.setattr(
        "scripts.bootstrap_via_runpod.resolve_data_center",
        lambda volume_id: "US-KS-2",
    )
    body = pod_body()
    assert body["dataCenterIds"] == ["US-KS-2"]


def test_bootstrap_script_serves_error_status():
    assert "trap" in BOOTSTRAP_SCRIPT
    assert "write_status error" in BOOTSTRAP_SCRIPT
    assert "write_status ok" in BOOTSTRAP_SCRIPT


def test_interpret_status_fails_fast_on_exited_pod():
    assert interpret_status({"state": "ok"}, None) == "ok"
    assert interpret_status({"state": "error", "message": "boom"}, None) == "error"
    assert interpret_status(None, {"desiredStatus": "EXITED"}) == "error"
    assert interpret_status(None, {"desiredStatus": "RUNNING"}) == "wait"


def test_template_runs_handler_from_volume():
    body = template_body("ls250824/run-comfyui-minimax:08092026")
    assert body["dockerEntrypoint"][0] == "/bin/bash"
    assert body["dockerEntrypoint"][1] == "-lc"
    assert "start_from_volume.sh" in body["dockerEntrypoint"][2]
    assert body["dockerStartCmd"] == []


def test_volume_start_script_uses_repo_on_volume():
    text = Path("worker/start_from_volume.sh").read_text(encoding="utf-8")
    assert "/runpod-volume/nsfw_prompts" in text
    assert "handler.py" in text
    text = Path("scripts/on_pod.sh").read_text(encoding="utf-8")
    assert "validate_volume.py" in text
    assert "validate_volume.py || true" not in text
    yaml = Path("worker/extra_model_paths.yaml").read_text(encoding="utf-8")
    assert "base_path: /runpod-volume" in yaml
    assert "base_path: /workspace" in yaml
    assert "base_path: /workspace/ComfyUI" in yaml


def test_endpoint_pins_volume_datacenter(monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "k")
    monkeypatch.setattr(
        "scripts.provision_runpod.resolve_data_center",
        lambda volume_id: "EU-RO-1",
    )
    body = endpoint_body("tpl_1", "vol_123")
    assert body["networkVolumeId"] == "vol_123"
    assert body["dataCenterIds"] == ["EU-RO-1"]
