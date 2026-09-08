from pathlib import Path

from minimax_r2v.download import download_weights, is_complete
from minimax_r2v.weights import expected_min_bytes


def test_truncated_file_is_incomplete(tmp_path):
    rel = "vae/minimax_h3_video_vae_fp16.safetensors"
    path = tmp_path / "models" / rel
    path.parent.mkdir(parents=True)
    path.write_bytes(b"0" * 2_000_000)
    assert is_complete(path, rel) is False
    assert expected_min_bytes(rel) > 5_000_000_000


def test_download_replaces_truncated_and_links_aliases(tmp_path, monkeypatch):
    monkeypatch.setattr("minimax_r2v.download.expected_min_bytes", lambda rel: 50)

    def fake_hub_download(repo_id, filename, token=None, local_dir=None, cache_dir=None):
        dest = Path(cache_dir or local_dir) / Path(filename).name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"1" * 80)
        return str(dest)

    truncated = tmp_path / "models" / "vae" / "minimax_h3_video_vae_fp16.safetensors"
    truncated.parent.mkdir(parents=True)
    truncated.write_bytes(b"x" * 10)

    saved = download_weights(tmp_path, hub_download=fake_hub_download)
    assert len(saved) == 5
    assert all(path.stat().st_size >= 50 for path in saved)
    assert (tmp_path / "models" / "unet" / "minimax_h3_ref2va_pruned_int8_convrot.safetensors").is_symlink()
    assert not (tmp_path / "models" / ".hf-cache").exists()
