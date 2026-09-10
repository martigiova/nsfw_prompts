from minimax_r2v.frames import h3_frame_count
import pytest


def test_eight_seconds_is_192_frames():
    assert h3_frame_count(8) == 192


def test_aligns_to_17n_plus_5():
    frames = h3_frame_count(1)
    assert frames % 17 == 5
    assert frames >= 5


def test_rejects_non_positive():
    with pytest.raises(ValueError):
        h3_frame_count(0)
