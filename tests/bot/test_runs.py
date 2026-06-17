from bot.runs import RUN_TYPES, is_run, filter_runs

def test_run_types_sao_os_tres():
    assert RUN_TYPES == {"running", "treadmill_running", "trail_running"}

def test_is_run_aceita_raw_garmin_e_db_row():
    assert is_run({"activityType": {"typeKey": "running"}})        # raw garmin
    assert is_run({"type": "treadmill_running"})                   # db row
    assert is_run({"type": "trail_running"})

def test_is_run_recusa_musculacao_e_cardio():
    assert not is_run({"type": "indoor_cardio"})                   # musculação
    assert not is_run({"activityType": {"typeKey": "strength_training"}})
    assert not is_run({"type": "lap_swimming"})
    assert not is_run({})

def test_filter_runs_preserva_ordem_e_so_corridas():
    acts = [
        {"activityId": 1, "type": "running"},
        {"activityId": 2, "type": "indoor_cardio"},
        {"activityId": 3, "activityType": {"typeKey": "trail_running"}},
    ]
    out = filter_runs(acts)
    assert [a.get("activityId") for a in out] == [1, 3]
