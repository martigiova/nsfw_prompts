from pathlib import Path

from minimax_r2v.volume import (
    assert_weights_if_volume_present,
    find_weight,
    missing_weights,
    volume_is_present,
)


def _touch_weight(root: Path, rel: str, size: int = 2_000_000) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"0" * size)


def test_missing_weights_on_empty_tree(tmp_path):
    assert missing_weights([tmp_path / "models"]) == [
        "diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors",
        "text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors",
        "vae/minimax_h3_video_vae_fp16.safetensors",
        "vae/minimax_h3_audio_vae_fp32.safetensors",
        "loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors",
    ]


def test_finds_required_weights(tmp_path, monkeypatch):
    monkeypatch.setattr("minimax_r2v.volume.expected_min_bytes", lambda rel: 1_000_000)
    models = tmp_path / "models"
    for rel in (
        "diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors",
        "text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors",
        "vae/minimax_h3_video_vae_fp16.safetensors",
        "vae/minimax_h3_audio_vae_fp32.safetensors",
        "loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors",
    ):
        _touch_weight(models, rel)
    assert missing_weights([models]) == []
    found = find_weight("vae/minimax_h3_video_vae_fp16.safetensors", [models])
    assert found is not None


def test_two_megabyte_stub_is_not_a_real_vae(tmp_path):
    models = tmp_path / "models"
    _touch_weight(models, "vae/minimax_h3_video_vae_fp16.safetensors", size=2_000_000)
    assert find_weight("vae/minimax_h3_video_vae_fp16.safetensors", [models]) is None


def test_volume_check_skipped_without_mount(monkeypatch):
    monkeypatch.delenv("VOLUME_ROOT", raising=False)
    monkeypatch.delenv("SKIP_VOLUME_CHECK", raising=False)
    monkeypatch.setattr("minimax_r2v.volume.volume_is_present", lambda: False)
    assert_weights_if_volume_present()


def test_volume_check_raises_when_mounted_and_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("VOLUME_ROOT", str(tmp_path))
    monkeypatch.delenv("SKIP_VOLUME_CHECK", raising=False)
    try:
        assert_weights_if_volume_present()
        raise AssertionError("should have raised")
    except RuntimeError as exc:
        assert "minimax_h3_ref2va" in str(exc)


def test_volume_is_present_uses_volume_root(monkeypatch, tmp_path):
    monkeypatch.setenv("VOLUME_ROOT", str(tmp_path))
    assert volume_is_present() is True
