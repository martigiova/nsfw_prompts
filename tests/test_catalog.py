from scripts.runpod_catalog import pick_serverless_dc


def test_pick_serverless_dc_prefers_high_stock_with_volumes():
    datacenters = {
        "dataCenters": [
            {"id": "EU-RO-1", "networkVolumeTypes": ["STANDARD"], "globalNetwork": True},
            {"id": "US-IL-1", "networkVolumeTypes": ["STANDARD"], "globalNetwork": True},
            {"id": "EU-CZ-1", "networkVolumeTypes": [], "globalNetwork": True},
        ]
    }
    gpus = {
        "gpus": [
            {
                "id": "NVIDIA RTX PRO 6000 Blackwell Server Edition",
                "dataCenters": [
                    {"id": "EU-RO-1", "availability": "LOW"},
                    {"id": "US-IL-1", "availability": "HIGH"},
                    {"id": "EU-CZ-1", "availability": "HIGH"},
                ],
            }
        ]
    }
    assert pick_serverless_dc(datacenters=datacenters, gpus=gpus) == "US-IL-1"


def test_pick_serverless_dc_skips_none_stock():
    datacenters = {
        "dataCenters": [
            {"id": "EU-RO-1", "networkVolumeTypes": ["STANDARD"], "globalNetwork": True},
        ]
    }
    gpus = {
        "gpus": [
            {
                "id": "NVIDIA RTX PRO 6000 Blackwell Server Edition",
                "dataCenters": [{"id": "EU-RO-1", "availability": "NONE"}],
            }
        ]
    }
    try:
        pick_serverless_dc(datacenters=datacenters, gpus=gpus)
        raise AssertionError("should have failed")
    except SystemExit as exc:
        assert "No Network-Volume data center" in str(exc)
