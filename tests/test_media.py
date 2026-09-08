from pathlib import Path

from minimax_r2v.media import safe_filename, unique_path


def test_safe_filename_strips_paths_and_spaces():
    assert safe_filename("../../evil name.png") == "evil_name.png"
    assert safe_filename("") == "file.bin"


def test_unique_path_increments(tmp_path: Path):
    first = unique_path(tmp_path, "clip.mp4")
    first.write_text("a")
    second = unique_path(tmp_path, "clip.mp4")
    assert first.name == "clip.mp4"
    assert second.name == "clip_1.mp4"
