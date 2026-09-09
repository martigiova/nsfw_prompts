from pathlib import Path

from minimax_r2v.media import download_media, safe_filename, unique_path
from minimax_r2v.payload import MediaRef


def test_safe_filename_strips_paths_and_spaces():
    assert safe_filename("../../evil name.png") == "evil_name.png"
    assert safe_filename("") == "file.bin"


def test_unique_path_increments(tmp_path: Path):
    first = unique_path(tmp_path, "clip.mp4")
    first.write_text("a")
    second = unique_path(tmp_path, "clip.mp4")
    assert first.name == "clip.mp4"
    assert second.name == "clip_1.mp4"


def test_download_sends_user_agent(tmp_path, monkeypatch):
    seen = {}

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size=1024):
            yield b"png"

    def fake_get(url, stream=True, timeout=120, headers=None):
        seen["headers"] = headers
        seen["url"] = url
        return FakeResp()

    monkeypatch.setattr("minimax_r2v.media.requests.get", fake_get)
    saved = download_media(
        [MediaRef(kind="image", url="https://cdn.example.com/face.png", filename="face.png")],
        tmp_path,
    )
    assert saved[0][1] == "face.png"
    assert seen["headers"]["User-Agent"] == "minimax-r2v/1.0"
