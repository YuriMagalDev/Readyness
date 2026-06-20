from src.metric_catalog import CATALOG, CATALOG_BY_KEY, MetricSpec, CADENCE_WINDOW_DAYS, by_domain
from src.metric_status import compute_status
import datetime


def test_catalog_keys_unique():
    keys = [m.key for m in CATALOG]
    assert len(keys) == len(set(keys))


def test_catalog_cadences_valid():
    valid = {"diaria", "corpo", "fitness", "evento"}
    assert all(m.cadencia in valid for m in CATALOG)


def test_catalog_domains_valid():
    valid = {"prontidao", "recuperacao", "atividade", "corpo", "checkin"}
    assert all(m.dominio in valid for m in CATALOG)


def test_catalog_has_expected_metrics():
    keys = {m.key for m in CATALOG}
    for k in ["vo2max", "sleep_hours", "resting_hr", "weight_kg",
              "steps", "hidratacao", "race_pred_5k"]:
        assert k in keys


def test_race_predictions_are_estimado():
    race = [m for m in CATALOG if m.key.startswith("race_pred_")]
    assert len(race) == 4
    assert all(m.source_default == "estimado" for m in race)


def test_checkins_are_manual():
    checkins = by_domain("checkin")
    assert {m.key for m in checkins} == {"hidratacao", "energia", "soreness", "alimentacao"}
    assert all(m.source_default == "manual" for m in checkins)


def test_cadence_windows():
    assert CADENCE_WINDOW_DAYS == {"diaria": 0, "corpo": 7, "fitness": 14}


def test_metricas_de_carga_no_catalogo():
    for key in ("acwr", "training_monotony", "resting_hr_baseline"):
        assert key in CATALOG_BY_KEY
        assert CATALOG_BY_KEY[key].source_default == "computed"


def test_computed_fresco_no_dia():
    spec = CATALOG_BY_KEY["acwr"]
    status = compute_status(spec.cadencia, "computed",
                            "2026-06-20T10:00:00", datetime.date(2026, 6, 20))
    assert status == "fresco"
