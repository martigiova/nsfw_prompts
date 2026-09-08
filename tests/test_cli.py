from minimax_r2v.cli import main


def test_check_validates_api_graph(capsys, monkeypatch):
    monkeypatch.delenv("VOLUME_ROOT", raising=False)
    monkeypatch.setattr("minimax_r2v.cli.volume_is_present", lambda: False)
    assert main(["check"]) == 0
    out = capsys.readouterr().out
    assert "workflow graph: OK" in out
