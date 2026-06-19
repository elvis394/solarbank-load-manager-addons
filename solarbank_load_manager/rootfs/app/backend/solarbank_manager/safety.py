from __future__ import annotations

from datetime import datetime, timezone

from .models import AppConfig, EntityState


def is_stale(state: EntityState | None, now: datetime, timeout_seconds: int) -> bool:
    if state is None or state.last_updated is None:
        return True
    if state.last_updated.tzinfo is None:
        last_updated = state.last_updated.replace(tzinfo=timezone.utc)
    else:
        last_updated = state.last_updated
    return (now - last_updated).total_seconds() > timeout_seconds


def validate_required_states(config: AppConfig, states: dict[str, EntityState], now: datetime) -> list[str]:
    timeout = config.control.stale_timeout_seconds
    missing: list[str] = []
    required = [
        config.smart_meter.import_power_entity,
        config.smart_meter.export_power_entity,
    ]
    for bank in config.banks:
        required.extend([bank.soc_entity, bank.ac_output_entity])
    for entity_id in [entity for entity in required if entity]:
        state = states.get(entity_id)
        if state is None:
            missing.append(f"{entity_id} fehlt")
        elif state.numeric_value() is None:
            missing.append(f"{entity_id} ist nicht numerisch")
        elif is_stale(state, now, timeout):
            missing.append(f"{entity_id} ist veraltet")
    return missing
