from unittest.mock import MagicMock
import tempfile, os
from src.garmin_client import GarminClient
from src.cache import Cache

def _gc():
    gc = GarminClient.__new__(GarminClient)
    gc._cache = Cache(db_path=os.path.join(tempfile.mkdtemp(), "c.db"), ttl_hours=6)
    gc._client = MagicMock()
    return gc

def test_get_activities_fresh_ignora_cache():
    gc = _gc()
    gc._client.get_activities.return_value = [{"activityId": 1}]
    gc.get_activities(2)                      # popula cache
    gc.get_activities(2, fresh=True)          # fresh: refaz mesmo com cache
    assert gc._client.get_activities.call_count == 2

def test_get_activities_sem_fresh_usa_cache():
    gc = _gc()
    gc._client.get_activities.return_value = [{"activityId": 1}]
    gc.get_activities(2)
    gc.get_activities(2)
    assert gc._client.get_activities.call_count == 1
