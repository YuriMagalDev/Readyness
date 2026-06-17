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


def test_get_sleep_day_caches():
    gc = _client_with_stub()
    gc._client.get_sleep_data.return_value = {"dailySleepDTO": {"sleepTimeSeconds": 25200}}
    out = gc.get_sleep_day("2026-06-10")
    assert out == {"dailySleepDTO": {"sleepTimeSeconds": 25200}}
    gc.get_sleep_day("2026-06-10")
    assert gc._client.get_sleep_data.call_count == 1


def test_get_activity_exercise_sets_caches():
    gc = _client_with_stub()
    gc._client.get_activity_exercise_sets.return_value = {"exerciseSets": []}
    out = gc.get_activity_exercise_sets(123)
    assert out == {"exerciseSets": []}
    gc.get_activity_exercise_sets(123)
    assert gc._client.get_activity_exercise_sets.call_count == 1


def test_sleep_vazio_nao_cacheia_refaz_ate_vir_real():
    # sono ainda não processado (sleepTimeSeconds None) não pode ser cacheado:
    # próxima chamada re-busca e, quando vier o real, passa a servir do cache
    gc = _client_with_stub()
    gc._client.get_sleep_data.side_effect = [
        {"dailySleepDTO": {"sleepTimeSeconds": None}},   # vazio -> não cacheia
        {"dailySleepDTO": {"sleepTimeSeconds": 29400}},  # real -> cacheia
    ]
    assert gc.get_sleep_day("2026-06-17")["dailySleepDTO"]["sleepTimeSeconds"] is None
    assert gc.get_sleep_day("2026-06-17")["dailySleepDTO"]["sleepTimeSeconds"] == 29400
    assert gc._client.get_sleep_data.call_count == 2
    gc.get_sleep_day("2026-06-17")  # agora vem do cache
    assert gc._client.get_sleep_data.call_count == 2
