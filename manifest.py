from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def load_manifest(path: Path) -> dict[str, Any]:
    return load_json(path, default={})


def save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    save_json(path, manifest)
