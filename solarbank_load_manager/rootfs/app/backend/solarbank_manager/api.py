from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .decisions import DecisionLog
from .ha_client import HomeAssistantClient
from .models import AppConfig, BankValues, Decision, EntityState, LiveState, Measurement
from .regulation import RegulationEngine
from .safety import validate_required_states
from .storage import Storage


class AppRuntime:
    def __init__(self) -> None:
        self.storage = Storage()
        self.config = self.storage.load_config()
        self.engine = RegulationEngine(self.config)
        self.decisions = DecisionLog()
        self.ha = HomeAssistantClient()
        self.latest_measurement: Measurement | None = None
        self.clients: set[WebSocket] = set()
        self.running = False

    async def broadcast(self) -> None:
        state = self.live_state().model_dump(mode="json")
        dead: list[WebSocket] = []
        for client in self.clients:
            try:
                await client.send_json(state)
            except Exception:
                dead.append(client)
        for client in dead:
            self.clients.discard(client)

    def live_state(self) -> LiveState:
        return LiveState(
            config=self.config,
            latest_measurement=self.latest_measurement,
            latest_decision=self.decisions.latest(),
            decisions=self.decisions.list(100),
        )

    def update_config(self, config: AppConfig) -> None:
        self.config = config
        self.storage.save_config(config)
        self.engine.update_config(config)

    async def read_measurement(self) -> tuple[Measurement | None, list[str], dict[str, EntityState]]:
        all_states = {state.entity_id: state for state in await self.ha.get_states()}
        now = datetime.now(timezone.utc)
        warnings = validate_required_states(self.config, all_states, now)
        import_state = all_states.get(self.config.smart_meter.import_power_entity)
        export_state = all_states.get(self.config.smart_meter.export_power_entity)
        if warnings or import_state is None or export_state is None:
            return None, warnings or ["Smart-Meter-Entities fehlen"], all_states

        bank_values: list[BankValues] = []
        for bank in self.config.banks:
            soc = all_states.get(bank.soc_entity)
            pv = all_states.get(bank.pv_power_entity)
            ac = all_states.get(bank.ac_output_entity)
            bank_values.append(
                BankValues(
                    name=bank.name,
                    soc_percent=soc.numeric_value() if soc else None,
                    pv_power_w=pv.numeric_value() if pv else None,
                    ac_output_w=ac.numeric_value() if ac else None,
                    last_written_w=self.engine.last_written.get(bank.name, 0),
                    setpoint_entity=bank.setpoint_entity,
                )
            )
        return (
            Measurement(
                time=now,
                grid_import_w=import_state.numeric_value() or 0,
                grid_export_w=export_state.numeric_value() or 0,
                banks=bank_values,
            ),
            warnings,
            all_states,
        )

    async def cycle_once(self) -> Decision:
        measurement, warnings, _ = await self.read_measurement()
        if measurement is None:
            decision = Decision(
                rules=warnings,
                failsafe=True,
                dry_run=self.config.control.dry_run,
                manual_override=self.config.control.manual_override,
            )
            self.decisions.append(decision)
            await self.broadcast()
            return decision

        self.latest_measurement = measurement
        decision = self.engine.decide(measurement)
        if not decision.dry_run and not decision.manual_override and not decision.failsafe:
            await self.write_targets(decision)
        self.decisions.append(decision)
        await self.broadcast()
        return decision

    async def write_targets(self, decision: Decision) -> None:
        bank_by_name = {bank.name: bank for bank in self.config.banks}
        for item in decision.banks:
            bank = bank_by_name.get(item.name)
            if bank is None or not bank.setpoint_entity:
                continue
            await self.ha.set_value(bank.setpoint_entity, item.final_target_w, bank.setpoint_domain)

    async def loop(self) -> None:
        if self.running:
            return
        self.running = True
        while self.running:
            try:
                await self.cycle_once()
            except Exception as exc:
                self.decisions.append(
                    Decision(
                        rules=[f"Regelzyklus fehlgeschlagen: {exc}"],
                        failsafe=True,
                        dry_run=self.config.control.dry_run,
                    )
                )
                await self.broadcast()
            await asyncio.sleep(self.config.control.regulation_interval_seconds)


class ManualSetpoint(BaseModel):
    bank: str
    value_w: float


def create_app() -> FastAPI:
    runtime = AppRuntime()
    app = FastAPI(title="Solarbank Load Manager", version="0.1.0")
    router = APIRouter(prefix="/api")

    @app.on_event("startup")
    async def startup() -> None:
        asyncio.create_task(runtime.loop())

    @router.get("/config", response_model=AppConfig)
    async def get_config() -> AppConfig:
        return runtime.config

    @router.put("/config", response_model=AppConfig)
    async def put_config(config: AppConfig) -> AppConfig:
        runtime.update_config(config)
        await runtime.broadcast()
        return config

    @router.get("/state", response_model=LiveState)
    async def get_state() -> LiveState:
        return runtime.live_state()

    @router.post("/cycle", response_model=Decision)
    async def cycle() -> Decision:
        return await runtime.cycle_once()

    @router.get("/entities", response_model=list[EntityState])
    async def entities() -> list[EntityState]:
        return await runtime.ha.get_states()

    @router.post("/override")
    async def override(enabled: bool) -> dict[str, bool]:
        config = runtime.config.model_copy(deep=True)
        config.control.manual_override = enabled
        runtime.update_config(config)
        await runtime.broadcast()
        return {"manual_override": enabled}

    @router.post("/dry-run")
    async def dry_run(enabled: bool) -> dict[str, bool]:
        config = runtime.config.model_copy(deep=True)
        config.control.dry_run = enabled
        runtime.update_config(config)
        await runtime.broadcast()
        return {"dry_run": enabled}

    @router.post("/manual-setpoint")
    async def manual_setpoint(payload: ManualSetpoint) -> dict[str, float | str]:
        bank = next((item for item in runtime.config.banks if item.name == payload.bank), None)
        if bank is None:
            return {"error": "unknown bank", "value_w": payload.value_w}
        value = max(0, min(payload.value_w, bank.max_output_w, runtime.config.control.global_output_limit_w))
        if not runtime.config.control.dry_run:
            await runtime.ha.set_value(bank.setpoint_entity, value, bank.setpoint_domain)
        return {"bank": bank.name, "value_w": value}

    @router.post("/emergency-stop")
    async def emergency_stop() -> dict[str, str]:
        if not runtime.config.control.dry_run:
            for bank in runtime.config.banks:
                if bank.setpoint_entity:
                    await runtime.ha.set_value(bank.setpoint_entity, 0, bank.setpoint_domain)
        runtime.engine.last_written = {bank.name: 0 for bank in runtime.config.banks}
        await runtime.broadcast()
        return {"status": "stopped"}

    @router.websocket("/ws")
    async def websocket(websocket: WebSocket) -> None:
        await websocket.accept()
        runtime.clients.add(websocket)
        await websocket.send_json(runtime.live_state().model_dump(mode="json"))
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            runtime.clients.discard(websocket)

    app.include_router(router)

    static_dir = Path("/app/frontend/dist")
    if static_dir.exists():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

        @app.get("/{path:path}")
        async def index(path: str = "") -> FileResponse:
            target = static_dir / path
            if path and target.exists() and target.is_file():
                return FileResponse(target)
            return FileResponse(static_dir / "index.html")

    return app
