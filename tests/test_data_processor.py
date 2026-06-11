from src.data_processor import DataProcessor

def make_activity(activity_type: str, duration_seconds: int = 3600, hr_avg: int = 140):
    return {
        "activityType": {"typeKey": activity_type},
        "duration": duration_seconds,
        "averageHR": hr_avg,
        "startTimeLocal": "2026-06-10 07:00:00",
        "activityName": "Test Activity",
    }

def test_detects_strength_training():
    dp = DataProcessor()
    acts = [make_activity("strength_training")]
    result = dp.classify_activities(acts)
    assert result[0]["is_strength"] is True

def test_detects_indoor_cardio_as_strength():
    dp = DataProcessor()
    acts = [make_activity("indoor_cardio")]
    result = dp.classify_activities(acts)
    assert result[0]["is_strength"] is True

def test_running_is_not_strength():
    dp = DataProcessor()
    acts = [make_activity("running")]
    result = dp.classify_activities(acts)
    assert result[0]["is_strength"] is False

def test_resting_hr_average():
    dp = DataProcessor()
    hr_data = [
        {"restingHeartRate": 50},
        {"restingHeartRate": 54},
        {"restingHeartRate": 52},
    ]
    assert dp.resting_hr_avg(hr_data) == 52.0

def test_resting_hr_average_missing_data():
    dp = DataProcessor()
    hr_data = [{}, {"restingHeartRate": 60}]
    assert dp.resting_hr_avg(hr_data) == 60.0

def test_sleep_debt_hours():
    dp = DataProcessor()
    sleep_data = [
        {"dailySleepDTO": {"sleepTimeSeconds": 18000}},  # 5h
        {"dailySleepDTO": {"sleepTimeSeconds": 21600}},  # 6h
        {"dailySleepDTO": {"sleepTimeSeconds": 25200}},  # 7h
        {"dailySleepDTO": {"sleepTimeSeconds": 18000}},  # 5h
    ]
    assert dp.sleep_debt_hours(sleep_data) == 5.0

def test_morning_body_battery():
    dp = DataProcessor()
    battery_data = [[{"charged": 65, "drained": 0}], [{"charged": 72, "drained": 0}]]
    avg = dp.morning_body_battery(battery_data)
    assert avg == 68.5
