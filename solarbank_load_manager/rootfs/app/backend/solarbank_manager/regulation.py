from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from .models import AppConfig, BankConfig, BankDecision, BankValues, ControlConfig, Decision, Measurement


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


class RingBuffer:
    def __init__(self, max_hours: int = 24) -> None:
        self.max_age = timedelta(hours=max_hours)
        self.samples: deque[Measurement] = deque()

    def add(self, sample: Measurement) -> None:
        self.samples.append(sample)
        cutoff = sample.time - self.max_age
        while self.samples and self.samples[0].time < cutoff:
            self.samples.popleft()

    def since(self, now: datetime, minutes: int) -> list[Measurement]:
        cutoff = now - timedelta(minutes=minutes)
        return [sample for sample in self.samples if sample.time >= cutoff]


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0


def calculate_time_based_discharge_floor(now: datetime, min_soc: float = 20) -> float:
    minutes = now.hour * 60 + now.minute
    if minutes < 6 * 60:
        return min_soc
    if minutes < 14 * 60:
        return 70
    if minutes < 17 * 60:
        progress = (minutes - 14 * 60) / (3 * 60)
        return 70 - progress * 25
    if minutes < 23 * 60 + 30:
        progress = (minutes - 17 * 60) / (6.5 * 60)
        return 45 - progress * 25
    return min_soc


def house_consumption_w(b14_ac_w: float, b16_ac_w: float, grid_import_w: float, grid_export_w: float) -> float:
    return max(0, b14_ac_w + b16_ac_w + grid_import_w - grid_export_w)


@dataclass
class Averages:
    house_avg_w: float
    house_short_w: float
    pv_by_bank_w: dict[str, float]


class RegulationEngine:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.buffer = RingBuffer()
        self.last_written: dict[str, float] = {bank.name: 0 for bank in config.banks}
        self.discharge_allowed: dict[str, bool] = {bank.name: True for bank in config.banks}

    def update_config(self, config: AppConfig) -> None:
        self.config = config
        for bank in config.banks:
            self.last_written.setdefault(bank.name, 0)
            self.discharge_allowed.setdefault(bank.name, True)

    def add_sample(self, sample: Measurement) -> None:
        self.buffer.add(sample)

    def averages(self, now: datetime, control: ControlConfig) -> Averages:
        window_samples = self.buffer.since(now, control.window_minutes)
        short_samples = self.buffer.since(now, control.short_window_minutes)
        pv_by_bank: dict[str, float] = {}
        for bank in self.config.banks:
            values = [
                next((b.pv_power_w or 0 for b in sample.banks if b.name == bank.name), 0)
                for sample in window_samples
            ]
            pv_by_bank[bank.name] = mean(values)
        return Averages(
            house_avg_w=mean([sample.house_consumption_w for sample in window_samples]),
            house_short_w=mean([sample.house_consumption_w for sample in short_samples]),
            pv_by_bank_w=pv_by_bank,
        )

    def decide(self, sample: Measurement) -> Decision:
        self.add_sample(sample)
        control = self.config.control
        averages = self.averages(sample.time, control)
        discharge_floor = calculate_time_based_discharge_floor(sample.time, control.min_soc_percent)
        raw_target = 0.70 * averages.house_avg_w + 0.30 * averages.house_short_w - control.safety_grid_import_reserve_w
        target_total = clamp(raw_target, 0, control.global_output_limit_w)

        rules = [
            f"Netzbilanz {sample.grid_balance_w:.0f} W",
            f"Ziel aus Durchschnitt {averages.house_avg_w:.0f} W und Kurzfenster {averages.house_short_w:.0f} W",
            f"Entladegrenze {discharge_floor:.0f} %",
        ]
        if control.dry_run:
            rules.append("Dry Run aktiv: keine Schreibzugriffe")
        if control.manual_override:
            rules.append("Manueller Override aktiv: Automatik schreibt nicht")

        max_allowed = self._bank_limits(sample, discharge_floor, control, rules)
        raw_targets = self._distribute(target_total, sample, max_allowed, rules)
        final_targets = self._apply_deadband_ramp(raw_targets, control)
        final_targets = self._enforce_global_limit(final_targets, control.global_output_limit_w)

        bank_decisions = []
        for bank in self.config.banks:
            values = self._values_for(sample, bank.name)
            allowed = max_allowed[bank.name] > 0
            bank_decisions.append(
                BankDecision(
                    name=bank.name,
                    available=values is not None,
                    discharge_allowed=self.discharge_allowed.get(bank.name, False),
                    max_allowed_w=max_allowed[bank.name],
                    raw_target_w=raw_targets.get(bank.name, 0),
                    final_target_w=final_targets.get(bank.name, 0),
                    last_written_w=self.last_written.get(bank.name, 0),
                    reason=None if allowed else "gesperrt oder keine sichere Leistung verfuegbar",
                )
            )

        decision = Decision(
            inputs={
                "grid_import_w": sample.grid_import_w,
                "grid_export_w": sample.grid_export_w,
                **{f"{bank.name.lower()}_ac_w": bank.ac_output_w for bank in sample.banks},
                **{f"{bank.name.lower()}_soc": bank.soc_percent for bank in sample.banks},
            },
            calculated={
                "house_now_w": sample.house_consumption_w,
                "house_avg_w": averages.house_avg_w,
                "house_short_w": averages.house_short_w,
                "target_total_w": target_total,
                "discharge_floor_percent": discharge_floor,
            },
            rules=rules,
            output={f"{name.lower()}_target_w": value for name, value in final_targets.items()},
            banks=bank_decisions,
            dry_run=control.dry_run,
            manual_override=control.manual_override,
        )

        if not control.dry_run and not control.manual_override:
            self.last_written.update(final_targets)
        return decision

    def _bank_limits(
        self,
        sample: Measurement,
        discharge_floor: float,
        control: ControlConfig,
        rules: list[str],
    ) -> dict[str, float]:
        limits: dict[str, float] = {}
        for bank in self.config.banks:
            values = self._values_for(sample, bank.name)
            if values is None:
                limits[bank.name] = 0
                rules.append(f"{bank.name}: keine Werte")
                continue

            soc = values.soc_percent
            pv = max(0, values.pv_power_w or 0)
            if soc is None:
                battery_allowed = False
                rules.append(f"{bank.name}: SOC fehlt")
            else:
                previous = self.discharge_allowed.get(bank.name, True)
                if soc <= control.min_soc_percent:
                    battery_allowed = False
                elif soc >= control.min_soc_percent + 2:
                    battery_allowed = True
                else:
                    battery_allowed = previous
                battery_allowed = battery_allowed and soc >= discharge_floor
                if soc >= control.target_max_soc_percent:
                    battery_allowed = True
                    rules.append(f"{bank.name}: SOC ueber Zielbereich, Leistung eher freigeben")
            self.discharge_allowed[bank.name] = battery_allowed

            direct_pv_limit = pv
            battery_limit = bank.max_output_w if battery_allowed else 0
            limits[bank.name] = clamp(max(direct_pv_limit, battery_limit), 0, bank.max_output_w)
            if direct_pv_limit > 0 and not battery_allowed:
                rules.append(f"{bank.name}: direkte PV-Nutzung trotz geschonter Batterie")
        return limits

    def _distribute(
        self,
        target_total: float,
        sample: Measurement,
        max_allowed: dict[str, float],
        rules: list[str],
    ) -> dict[str, float]:
        if self.config.control.mode == "b14_leader_b16_follower":
            b14 = self._values_for(sample, "B14")
            b14_ac = max(0, b14.ac_output_w or 0) if b14 else 0
            remaining = target_total - b14_ac
            rules.append("B14 Fuehrungsbank, B16 ergaenzt Restbedarf")
            return {
                "B14": clamp(min(b14_ac, max_allowed.get("B14", 0)), 0, max_allowed.get("B14", 0)),
                "B16": clamp(remaining, 0, max_allowed.get("B16", 0)),
            }

        weights: dict[str, float] = {}
        for bank in self.config.banks:
            values = self._values_for(sample, bank.name)
            if values is None or max_allowed.get(bank.name, 0) <= 0:
                weights[bank.name] = 0
                continue
            soc = values.soc_percent or 0
            pv = max(0, values.pv_power_w or 0)
            usable_energy = bank.capacity_wh * max(0, soc - self.config.control.min_soc_percent) / 100
            weights[bank.name] = usable_energy + self.config.control.direct_pv_bias_w * pv
        total_weight = sum(weights.values())
        if total_weight <= 0:
            return {bank.name: 0 for bank in self.config.banks}
        rules.append("Zentrale Verteilung nach Kapazitaet, SOC und PV")
        return {
            bank.name: clamp(target_total * weights[bank.name] / total_weight, 0, max_allowed.get(bank.name, 0))
            for bank in self.config.banks
        }

    def _apply_deadband_ramp(self, raw_targets: dict[str, float], control: ControlConfig) -> dict[str, float]:
        final: dict[str, float] = {}
        for name, target in raw_targets.items():
            last = self.last_written.get(name, 0)
            if abs(target - last) < control.deadband_w:
                final[name] = last
            else:
                delta = clamp(target - last, -control.max_step_w, control.max_step_w)
                final[name] = last + delta
        return final

    def _enforce_global_limit(self, targets: dict[str, float], limit: float) -> dict[str, float]:
        total = sum(targets.values())
        if total <= limit or total <= 0:
            return targets
        factor = limit / total
        return {name: value * factor for name, value in targets.items()}

    def _values_for(self, sample: Measurement, name: str) -> BankValues | None:
        return next((bank for bank in sample.banks if bank.name == name), None)
