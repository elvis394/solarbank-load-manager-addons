from __future__ import annotations

import json
from pathlib import Path

from .models import AppConfig


class Storage:
    def __init__(self, path: Path = Path("/data/config.json"), options_path: Path = Path("/data/options.json")) -> None:
        self.path = path
        self.options_path = options_path

    def load_config(self) -> AppConfig:
        if not self.path.exists():
            return self._apply_addon_options(AppConfig())
        return self._apply_addon_options(AppConfig.model_validate_json(self.path.read_text(encoding="utf-8")))

    def save_config(self, config: AppConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(config.model_dump(mode="json"), indent=2), encoding="utf-8")

    def _apply_addon_options(self, config: AppConfig) -> AppConfig:
        if not self.options_path.exists():
            return config
        try:
            options = json.loads(self.options_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return config
        control = config.control.model_copy(update={
            "dry_run": options.get("dry_run", config.control.dry_run),
            "regulation_interval_seconds": options.get(
                "regulation_interval_seconds",
                config.control.regulation_interval_seconds,
            ),
            "global_output_limit_w": options.get("global_output_limit_w", config.control.global_output_limit_w),
        })
        return config.model_copy(update={"control": control})
