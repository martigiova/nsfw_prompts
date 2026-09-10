from minimax_r2v.airtable import AirtableClient, PENDING_STATUSES


def test_mark_done_sends_attachment_url(monkeypatch):
    seen = {}

    def fake_patch(url, headers=None, json=None, timeout=30):
        seen["url"] = url
        seen["json"] = json

        class Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return {"ok": True}

        return Resp()

    monkeypatch.setattr("minimax_r2v.airtable.requests.patch", fake_patch)
    client = AirtableClient(token="tok", base_id="appX", table="Generazioni")
    client.mark_done("rec1", "https://cdn.example.com/out.mp4", "out.mp4")
    assert "rec1" in seen["url"]
    fields = seen["json"]["fields"]
    assert fields["Status"] == "Done"
    assert fields["Output"] == "https://cdn.example.com/out.mp4"


def test_airtable_honors_env_field_names(monkeypatch):
    seen = {}

    def fake_patch(url, headers=None, json=None, timeout=30):
        seen["json"] = json

        class Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return {"ok": True}

        return Resp()

    monkeypatch.setattr("minimax_r2v.airtable.requests.patch", fake_patch)
    monkeypatch.setenv("AIRTABLE_STATUS_FIELD", "Stato")
    monkeypatch.setenv("AIRTABLE_OUTPUT_FIELD", "Video")
    client = AirtableClient(token="tok", base_id="appX", table="Generazioni")
    client.mark_done("rec1", "https://cdn.example.com/out.mp4", "out.mp4")
    fields = seen["json"]["fields"]
    assert fields["Stato"] == "Done"
    assert "Status" not in fields
    assert fields["Video"] == "https://cdn.example.com/out.mp4"


def test_list_pending_filters_todo_and_queued(monkeypatch):
    seen = {}

    def fake_get(url, headers=None, params=None, timeout=30):
        seen["url"] = url
        seen["params"] = params

        class Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return {"records": [{"id": "recTodo", "fields": {"Status": "Todo"}}]}

        return Resp()

    monkeypatch.setattr("minimax_r2v.airtable.requests.get", fake_get)
    client = AirtableClient(token="tok", base_id="appX", table="Minimax")
    rows = client.list_pending()
    assert rows[0]["id"] == "recTodo"
    formula = seen["params"]["filterByFormula"]
    assert "{Status}='Todo'" in formula
    assert "{Status}='Queued'" in formula
    assert PENDING_STATUSES == ("Todo", "Queued")
