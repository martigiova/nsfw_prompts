from minimax_r2v.resolution import parse_aspect, resolution_from_aspect


def test_portrait_is_multiple_of_32():
    width, height = resolution_from_aspect("9:16")
    assert width % 32 == 0
    assert height % 32 == 0
    assert height > width
    assert width == 736
    assert height == 1344


def test_landscape_and_square():
    w, h = resolution_from_aspect("16:9")
    assert w > h
    w, h = resolution_from_aspect("1:1")
    assert w == h


def test_alias_portrait():
    assert parse_aspect("9:16 (Portrait Widescreen)") == (9, 16)
