from datetime import datetime, timezone

from solarbank_manager.models import AppConfig, BankValues, Measurement
from solarbank_manager.regulation import RegulationEngine


def make_sample(import_w: float) -> Measurement:
    return Measurement(
        time=datetime(2026, 6, 19, 20, 0, tzinfo=timezone.utc),
        grid_import_w=import_w,
        grid_export_w=0,
        banks=[
            BankValues(name="B14", soc_percent=80, pv_power_w=0, ac_output_w=0),
            BankValues(name="B16", soc_percent=80, pv_power_w=0, ac_output_w=0),
        ],
    )


def test_ramp_limits_first_step() -> None:
    config = AppConfig()
    config.control.mode = "central"
    config.control.max_step_w = 50
    config.control.deadband_w = 0
    engine = RegulationEngine(config)

    decision = engine.decide(make_sample(800))

    assert max(decision.output.values()) <= 50


def test_deadband_keeps_last_written_value() -> None:
    config = AppConfig()
    config.control.mode = "central"
    config.control.max_step_w = 1000
    config.control.deadband_w = 20
    config.control.dry_run = False
    engine = RegulationEngine(config)
    engine.decide(make_sample(500))

    second = engine.decide(make_sample(505))

    assert second.output == {"b14_target_w": engine.last_written["B14"], "b16_target_w": engine.last_written["B16"]}
