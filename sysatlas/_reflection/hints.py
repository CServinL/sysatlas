"""Load an optional sysatlas hints file from the scan root."""
from __future__ import annotations

import json
from pathlib import Path

from sysatlas._reflection.reflection import Hints


_CANDIDATES = ("sysatlas.json", "sysatlas.yaml", "sysatlas.yml")


def load_hints(root: str | Path) -> Hints | None:
    """Look for a hints file at root. JSON always supported; YAML if PyYAML installed."""
    root_path = Path(root).resolve()
    base = root_path if root_path.is_dir() else root_path.parent
    for name in _CANDIDATES:
        path = base / name
        if not path.exists():
            continue
        return _parse(path)
    return None


def _parse(path: Path) -> Hints:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                f"{path.name} found but PyYAML is not installed. "
                "Install PyYAML or use sysatlas.json instead."
            ) from e
        data = yaml.safe_load(text) or {}
    return Hints(**data)
