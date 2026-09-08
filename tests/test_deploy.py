from scripts.bootstrap_via_runpod import pod_body, start_command
from scripts.deploy import check


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
    monkeypatch.setenv("RUNPOD_NETWORK_VOLUME_ID", "vol_123")
    monkeypatch.setenv("GIT_REF", "cursor/minimax-runpod-serverless-9e74")
    body = pod_body()
    assert body["imageName"] == "runpod/base:1.1.0-ubuntu2204"
    assert body["computeType"] == "CPU"
    assert body["networkVolumeId"] == "vol_123"
    assert body["volumeMountPath"] == "/workspace"
    assert body["dockerStartCmd"] == start_command()
    script = body["dockerStartCmd"][2]
    assert "scripts/on_pod.sh" in script
    assert "validate_volume.py" in script
    assert body["env"]["GIT_REF"] == "cursor/minimax-runpod-serverless-9e74"
