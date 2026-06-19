from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import httpx

from .models import EntityState


class HomeAssistantClient:
    def __init__(self, base_url: str = "http://supervisor/core/api", token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token or os.environ.get("SUPERVISOR_TOKEN", "")

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    async def get_state(self, entity_id: str) -> EntityState:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{self.base_url}/states/{entity_id}", headers=self.headers)
            response.raise_for_status()
            return self._parse_state(response.json())

    async def get_states(self) -> list[EntityState]:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(f"{self.base_url}/states", headers=self.headers)
            response.raise_for_status()
            return [self._parse_state(item) for item in response.json()]

    async def call_service(self, domain: str, service: str, data: dict[str, Any]) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{self.base_url}/services/{domain}/{service}",
                headers=self.headers,
                json=data,
            )
            response.raise_for_status()

    async def set_value(self, entity_id: str, value: float, domain: str = "number") -> None:
        service_domain = "input_number" if domain == "input_number" else "number"
        await self.call_service(service_domain, "set_value", {"entity_id": entity_id, "value": round(value, 1)})

    def _parse_state(self, payload: dict[str, Any]) -> EntityState:
        last_updated = payload.get("last_updated")
        return EntityState(
            entity_id=payload["entity_id"],
            state=payload.get("state", "unknown"),
            attributes=payload.get("attributes", {}),
            last_updated=datetime.fromisoformat(last_updated.replace("Z", "+00:00")) if last_updated else None,
        )
