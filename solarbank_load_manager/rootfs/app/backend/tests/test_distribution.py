from datetime import datetime, timezone

from solarbank_manager.models import AppConfig, BankValues, Measurement
from solarbank_manager.regulation import RegulationEngine


def test_b14_leader_mode_lets_b16_fill_remaining_target() -> None:
    config = AppConfig()
    config.control.max_step_w = 1000
    config.control.deadband_w = 0
    engine = RegulationEngine(config)
    sample = Measurement(
        time=datetime(2026, 6, 19, 20, 0, tzinfo=timezone.utc),
        grid_import_w=300,
        grid_export_w=0,
        banks=[
            BankValues(name="B14", soc_percent=80, pv_power_w=0, ac_output_w=400),
            BankValues(name="B16", soc_percent=60, pv_power_w=0, ac_output_w=0),
        ],
    )

    decision = engine.decide(sample)

    assert decision.output["b14_target_w"] == 400
    assert decision.output["b16_target_w"] > 0
    assert sum(decision.output.values()) <= config.control.global_output_limit_w


def test_central_mode_weights_larger_available_bank_more() -> None:
    config = AppConfig()
    config.control.mode = "central"
    config.control.max_step_w = 1000
    config.control.deadband_w = 0
    engine = RegulationEngine(config)
    sample = Measurement(
        time=datetime(2026, 6, 19, 20, 0, tzinfo=timezone.utc),
        grid_import_w=700,
        grid_export_w=0,
        banks=[
            BankValues(name="B14", soc_percent=80, pv_power_w=0, ac_output_w=0),
            BankValues(name="B16", soc_percent=40, pv_power_w=0, ac_output_w=0),
        ],
    )

    decision = engine.decide(sample)

    assert decision.output["b14_target_w"] > decision.output["b16_target_w"]
