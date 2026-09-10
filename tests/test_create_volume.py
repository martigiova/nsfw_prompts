from scripts.create_volume import existing_named


def test_existing_named_matches_by_name(monkeypatch):
    monkeypatch.setattr(
        "scripts.create_volume.request",
        lambda method, path: [
            {"id": "old", "name": "other"},
            {"id": "new", "name": "minimax-h3-us-il-1"},
        ],
    )
    found = existing_named("minimax-h3-us-il-1")
    assert found is not None
    assert found["id"] == "new"
