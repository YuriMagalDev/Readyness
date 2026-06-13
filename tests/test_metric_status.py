import datetime
from src.metric_status import compute_status

TODAY = datetime.date(2026, 6, 13)


def test_estimado_overrides_everything():
    assert compute_status("fitness", "estimado", "2026-01-01T00:00", TODAY) == "estimado"


def test_ausente_when_no_measured_at():
    assert compute_status("diaria", "garmin", None, TODAY) == "ausente"


def test_diaria_fresco_today():
    assert compute_status("diaria", "garmin", "2026-06-13T06:40", TODAY) == "fresco"


def test_diaria_velho_yesterday():
    assert compute_status("diaria", "garmin", "2026-06-12T06:40", TODAY) == "velho"


def test_corpo_fresco_within_7_days():
    assert compute_status("corpo", "garmin", "2026-06-10T07:00", TODAY) == "fresco"


def test_corpo_velho_after_7_days():
    assert compute_status("corpo", "garmin", "2026-06-05T07:00", TODAY) == "velho"


def test_fitness_fresco_within_14_days():
    assert compute_status("fitness", "garmin", "2026-06-01T00:00", TODAY) == "fresco"


def test_fitness_velho_after_14_days():
    assert compute_status("fitness", "garmin", "2026-05-20T00:00", TODAY) == "velho"


def test_evento_always_fresco_if_present():
    assert compute_status("evento", "garmin", "2025-01-01T00:00", TODAY) == "fresco"
