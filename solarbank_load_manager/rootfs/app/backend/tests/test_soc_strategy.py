from datetime import datetime, timezone

from solarbank_manager.regulation import calculate_time_based_discharge_floor


def test_morning_keeps_battery_reserved() -> None:
    floor = calculate_time_based_discharge_floor(datetime(2026, 6, 19, 10, 0, tzinfo=timezone.utc))

    assert floor == 70


def test_afternoon_opens_linearly() -> None:
    floor = calculate_time_based_discharge_floor(datetime(2026, 6, 19, 15, 30, tzinfo=timezone.utc))

    assert 57 <= floor <= 58


def test_late_evening_uses_minimum_floor() -> None:
    floor = calculate_time_based_discharge_floor(datetime(2026, 6, 19, 23, 45, tzinfo=timezone.utc))

    assert floor == 20
