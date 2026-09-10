from minimax_r2v.comfy import ComfyClient


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.content = b""

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def test_queue_prompt_raises_on_node_errors(monkeypatch):
    client = ComfyClient()

    def fake_post(path, **kwargs):
        return FakeResponse(
            {
                "prompt_id": "p1",
                "node_errors": {"137": {"errors": [{"message": "lora missing"}]}},
            }
        )

    monkeypatch.setattr(client, "_post", fake_post)
    try:
        client.queue_prompt({"1": {}})
        raise AssertionError("should have raised")
    except RuntimeError as exc:
        assert "node_errors" in str(exc)


def test_wait_for_prompt_interrupts_on_timeout(monkeypatch):
    client = ComfyClient()
    seen = []

    def fake_get(path, **kwargs):
        return FakeResponse({})

    def fake_post(path, **kwargs):
        seen.append(path)
        return FakeResponse({})

    monkeypatch.setattr(client, "_get", fake_get)
    monkeypatch.setattr(client, "_post", fake_post)
    try:
        client.wait_for_prompt("missing", poll_interval=0.01, timeout=0.05)
        raise AssertionError("should have timed out")
    except TimeoutError as exc:
        assert "missing" in str(exc)
    assert "/interrupt" in seen
