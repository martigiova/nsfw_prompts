import pytest

from minimax_r2v.storage import public_url, s3_configured


def test_s3_configured_requires_public_prefix(monkeypatch):
    monkeypatch.setenv("BUCKET_ENDPOINT_URL", "https://xxx.r2.cloudflarestorage.com")
    monkeypatch.setenv("BUCKET_NAME", "minimax")
    monkeypatch.setenv("BUCKET_ACCESS_KEY_ID", "id")
    monkeypatch.setenv("BUCKET_SECRET_ACCESS_KEY", "secret")
    monkeypatch.delenv("BUCKET_PUBLIC_URL_PREFIX", raising=False)
    assert s3_configured() is False
    monkeypatch.setenv("BUCKET_PUBLIC_URL_PREFIX", "https://cdn.example.com")
    assert s3_configured() is True


def test_s3_configured_requires_access_keys(monkeypatch):
    monkeypatch.setenv("BUCKET_ENDPOINT_URL", "https://xxx.r2.cloudflarestorage.com")
    monkeypatch.setenv("BUCKET_NAME", "minimax")
    monkeypatch.setenv("BUCKET_PUBLIC_URL_PREFIX", "https://cdn.example.com")
    monkeypatch.delenv("BUCKET_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("BUCKET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("BUCKET_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("BUCKET_SECRET_KEY", raising=False)
    assert s3_configured() is False
    monkeypatch.setenv("BUCKET_ACCESS_KEY_ID", "id")
    monkeypatch.setenv("BUCKET_SECRET_ACCESS_KEY", "secret")
    assert s3_configured() is True


def test_public_url_keeps_slashes(monkeypatch):
    monkeypatch.setenv("BUCKET_PUBLIC_URL_PREFIX", "https://cdn.example.com/videos")
    url = public_url("minimax-r2v/job-1/out.mp4")
    assert url == "https://cdn.example.com/videos/minimax-r2v/job-1/out.mp4"


def test_public_url_rejects_api_endpoint_fallback(monkeypatch):
    monkeypatch.delenv("BUCKET_PUBLIC_URL_PREFIX", raising=False)
    with pytest.raises(RuntimeError, match="BUCKET_PUBLIC_URL_PREFIX"):
        public_url("minimax-r2v/job-1/out.mp4")
