"""Read a configuration file the user maintains (hints, intent) into a validated model.

Any problem with the file, whether unreadable, not decodable, not parseable, not an object, or
failing validation, raises one ValueError that names the file.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, TypeVar

from pydantic import BaseModel

M = TypeVar("M", bound=BaseModel)


def load_config(path: Path, kind: str, parse: Callable[[str], Any], model: type[M]) -> M:
    """Read `path` as UTF-8, `parse` the text into an object, and validate it as `model`."""
    try:
        data = parse(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"expected an object at the top level, got {type(data).__name__}")
        return model.model_validate(data)
    except Exception as e:  # every failure becomes one error that names the file
        raise ValueError(f"invalid {kind} file {path.name} ({path}): {e}") from e
