import time
import pytest
from src.cache import Cache

@pytest.fixture
def cache(tmp_path):
    return Cache(db_path=str(tmp_path / "test.db"), ttl_hours=0.001)  # ~3.6s TTL

def test_set_and_get(cache):
    cache.set("key1", {"value": 42})
    result = cache.get("key1")
    assert result == {"value": 42}

def test_get_missing_key(cache):
    assert cache.get("nonexistent") is None

def test_ttl_expiry(cache):
    cache.set("key2", {"value": 99})
    time.sleep(4)
    assert cache.get("key2") is None

def test_overwrite(cache):
    cache.set("key3", {"value": 1})
    cache.set("key3", {"value": 2})
    assert cache.get("key3") == {"value": 2}

def test_clear_empties_cache(tmp_path):
    from src.cache import Cache
    c = Cache(db_path=str(tmp_path / "c.db"), ttl_hours=6)
    c.set("k", {"v": 1})
    assert c.get("k") == {"v": 1}
    c.clear()
    assert c.get("k") is None
