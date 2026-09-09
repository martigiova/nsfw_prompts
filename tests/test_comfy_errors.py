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
