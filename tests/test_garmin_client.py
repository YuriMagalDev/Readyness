from unittest.mock import MagicMock


def _client_with_stub():
    # Evita login real: injeta cliente Garmin e cache em memória
    from src.garmin_client import GarminClient
    gc = GarminClient.__new__(GarminClient)  # sem __init__ (não autentica)
    from src.cache import Cache
    import tempfile, os
    gc._cache = Cache(db_path=os.path.join(tempfile.mkdtemp(), "c.db"), ttl_hours=6)
    gc._client = MagicMock()
    return gc


def test_get_training_readiness_caches():
    gc = _client_with_stub()
    gc._client.get_morning_training_readiness.return_value = {"score": 70}
    out = gc.get_training_readiness("2026-06-13")
    assert out == {"score": 70}
    gc.get_training_readiness("2026-06-13")  # 2ª vez = cache
    assert gc._client.get_morning_training_readiness.call_count == 1


def test_get_body_composition_caches():
    gc = _client_with_stub()
    gc._client.get_body_composition.return_value = {"dateWeightList": []}
    out = gc.get_body_composition("2026-06-06", "2026-06-13")
    assert out == {"dateWeightList": []}
    gc.get_body_composition("2026-06-06", "2026-06-13")
    assert gc._client.get_body_composition.call_count == 1
