import os

from minimax_r2v.queue import drain_airtable_queue


class FakeClient:
    def __init__(self, batches):
        self.enabled = True
        self.calls = 0
        self.batches = batches

    def list_pending(self):
        idx = min(self.calls, len(self.batches) - 1)
        self.calls += 1
        return list(self.batches[idx])


def test_drain_processes_pending_then_stops(monkeypatch):
    seen = []
    client = FakeClient(
        [
            [{"id": "recA"}, {"id": "recB"}],
            [],
            [],
        ]
    )
    monkeypatch.setattr("minimax_r2v.queue.AirtableClient", lambda: client)
    monkeypatch.setenv("AIRTABLE_IDLE_SECONDS", "0")
    monkeypatch.setenv("AIRTABLE_POLL_SECONDS", "0")
    monkeypatch.setenv("RUNPOD_POD_ID", "pod1")
    monkeypatch.delenv("AIRTABLE_RECORD_ID", raising=False)

    def fake_run(event):
        seen.append(event)
        return {"ok": True}

    monkeypatch.setattr("minimax_r2v.queue.run_job", fake_run)
    stats = drain_airtable_queue()
    ids = [event["input"]["airtable_record_id"] for event in seen]
    assert ids == ["recA", "recB"]
    assert seen[0]["id"] == "pod1-recA"
    assert stats == {"done": 2, "errors": 0}


def test_drain_runs_explicit_record_first(monkeypatch):
    client = FakeClient([[], []])
    monkeypatch.setattr("minimax_r2v.queue.AirtableClient", lambda: client)
    monkeypatch.setenv("AIRTABLE_IDLE_SECONDS", "0")
    monkeypatch.setenv("AIRTABLE_POLL_SECONDS", "0")
    monkeypatch.setenv("AIRTABLE_RECORD_ID", "recFirst")
    monkeypatch.setenv("RUNPOD_POD_ID", "pod9")
    events = []

    def fake_run(event):
        events.append(event)
        return {"ok": True}

    monkeypatch.setattr("minimax_r2v.queue.run_job", fake_run)
    drain_airtable_queue()
    assert events[0]["input"]["airtable_record_id"] == "recFirst"
    assert events[0]["id"] == "pod9-recFirst"
