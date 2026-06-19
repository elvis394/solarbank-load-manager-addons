from datetime import datetime, timezone

from solarbank_manager.models import AppConfig, EntityState
from solarbank_manager.safety import validate_required_states


def test_missing_required_states_report_warnings() -> None:
    config = AppConfig()
    config.smart_meter.import_power_entity = "sensor.import"
    config.smart_meter.export_power_entity = "sensor.export"
    config.banks[0].soc_entity = "sensor.b14_soc"
    config.banks[0].ac_output_entity = "sensor.b14_ac"

    warnings = validate_required_states(config, {}, datetime.now(timezone.utc))

    assert "sensor.import fehlt" in warnings
    assert "sensor.b14_soc fehlt" in warnings


def test_non_numeric_state_reports_warning() -> None:
    config = AppConfig()
    config.smart_meter.import_power_entity = "sensor.import"
    states = {
        "sensor.import": EntityState(
            entity_id="sensor.import",
            state="unknown",
            last_updated=datetime.now(timezone.utc),
        )
    }

    warnings = validate_required_states(config, states, datetime.now(timezone.utc))

    assert "sensor.import ist nicht numerisch" in warnings
