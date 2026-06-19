from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


SetpointDomain = Literal["number", "input_number"]
ControlMode = Literal["b14_leader_b16_follower", "central"]


class EntityMapping(BaseModel):
    entity_id: str = ""
    unit: str | None = None
    last_value: float | None = None
    last_updated: datetime | None = None
    available: bool = False


class SmartMeterConfig(BaseModel):
    import_power_entity: str = ""
    export_power_entity: str = ""


class BankConfig(BaseModel):
    name: str
    capacity_wh: float
    smart_meter_control: bool = False
    soc_entity: str = ""
    pv_power_entity: str = ""
    ac_output_entity: str = ""
    setpoint_entity: str = ""
    setpoint_domain: SetpointDomain = "number"
    max_output_w: float = 800


class ControlConfig(BaseModel):
    mode: ControlMode = "b14_leader_b16_follower"
    window_minutes: int = Field(default=60, ge=1, le=1440)
    short_window_minutes: int = Field(default=3, ge=1, le=60)
    regulation_interval_seconds: int = Field(default=15, ge=5, le=300)
    safety_grid_import_reserve_w: float = Field(default=30, ge=0)
    global_output_limit_w: float = Field(default=800, ge=0)
    deadband_w: float = Field(default=20, ge=0)
    max_step_w: float = Field(default=50, ge=0)
    min_soc_percent: float = Field(default=20, ge=0, le=100)
    target_max_soc_percent: float = Field(default=80, ge=0, le=100)
    stale_timeout_seconds: int = Field(default=900, ge=0)
    direct_pv_bias_w: float = Field(default=0.5, ge=0)
    dry_run: bool = True
    manual_override: bool = False


class AppConfig(BaseModel):
    smart_meter: SmartMeterConfig = Field(default_factory=SmartMeterConfig)
    banks: list[BankConfig] = Field(
        default_factory=lambda: [
            BankConfig(
                name="B14",
                capacity_wh=8000,
                smart_meter_control=True,
                max_output_w=800,
            ),
            BankConfig(name="B16", capacity_wh=3200, max_output_w=800),
        ]
    )
    control: ControlConfig = Field(default_factory=ControlConfig)


class EntityState(BaseModel):
    entity_id: str
    state: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    last_updated: datetime | None = None

    def numeric_value(self) -> float | None:
        try:
            return float(self.state)
        except (TypeError, ValueError):
            return None


class BankValues(BaseModel):
    name: str
    soc_percent: float | None = None
    pv_power_w: float | None = None
    ac_output_w: float | None = None
    last_written_w: float = 0
    setpoint_entity: str = ""


class Measurement(BaseModel):
    time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    grid_import_w: float
    grid_export_w: float
    banks: list[BankValues]

    @property
    def grid_balance_w(self) -> float:
        return self.grid_import_w - self.grid_export_w

    @property
    def house_consumption_w(self) -> float:
        ac_total = sum(max(0, bank.ac_output_w or 0) for bank in self.banks)
        return max(0, ac_total + self.grid_import_w - self.grid_export_w)


class BankDecision(BaseModel):
    name: str
    available: bool
    discharge_allowed: bool
    max_allowed_w: float
    raw_target_w: float
    final_target_w: float
    last_written_w: float
    reason: str | None = None


class Decision(BaseModel):
    time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    inputs: dict[str, Any] = Field(default_factory=dict)
    calculated: dict[str, Any] = Field(default_factory=dict)
    rules: list[str] = Field(default_factory=list)
    output: dict[str, float] = Field(default_factory=dict)
    banks: list[BankDecision] = Field(default_factory=list)
    dry_run: bool = True
    failsafe: bool = False
    manual_override: bool = False


class LiveState(BaseModel):
    config: AppConfig
    latest_measurement: Measurement | None = None
    latest_decision: Decision | None = None
    decisions: list[Decision] = Field(default_factory=list)
