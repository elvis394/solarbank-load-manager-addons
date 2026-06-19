from datetime import datetime, timezone

from solarbank_manager.models import AppConfig, BankValues, Measurement
from solarbank_manager.regulation import RegulationEngine


def test_dry_run_does_not_update_last_written() -> None:
    config = AppConfig()
    config.control.mode = "central"
    config.control.max_step_w = 1000
    config.control.deadband_w = 0
    config.control.dry_run = True
    engine = RegulationEngine(config)

    engine.decide(
        Measurement(
            time=datetime(2026, 6, 19, 20, 0, tzinfo=timezone.utc),
            grid_import_w=600,
            grid_export_w=0,
            banks=[
                BankValues(name="B14", soc_percent=80, pv_power_w=0, ac_output_w=0),
                BankValues(name="B16", soc_percent=80, pv_power_w=0, ac_output_w=0),
            ],
        )
    )

    assert engine.last_written == {"B14": 0, "B16": 0}
