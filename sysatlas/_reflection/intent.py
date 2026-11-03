"""The human / LLM-authored layer: what components are for and which patterns they follow.

Imports cannot show intent, so it is written down in a JSON file and merged
into the atlas, marked as not generated. Each component entry carries a
fingerprint of its members' public symbols; when the code changes shape the
entry is reported as stale so it gets re-read.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class IntentComponent(BaseModel):
    """What one component is for, plus the fingerprint it was written against."""
    model_config = ConfigDict(extra="forbid")

    purpose: str
    """One or two sentences: what the component is responsible for, and what it must not do."""
    fingerprint: str = ""
    """Value of the component's fingerprint when the purpose was written. Empty = never checked."""
    patterns: list[str] = Field(default_factory=list)
    """Names of entries in `Intent.patterns` that this component takes part in."""


class IntentPattern(BaseModel):
    """An architectural pattern: its name, how it appears here, and the components involved."""
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    components: list[str] = Field(default_factory=list)


class Intent(BaseModel):
    """The hand- or LLM-written overlay: system summary, component purposes and patterns."""
    model_config = ConfigDict(extra="forbid")

    summary: str = ""
    """What the whole system is for, in a short paragraph."""
    components: dict[str, IntentComponent] = Field(default_factory=dict)
    patterns: list[IntentPattern] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_pattern_references(self) -> "Intent":
        names = [p.name for p in self.patterns]
        if len(set(names)) != len(names):
            raise ValueError("intent: pattern names must be unique")
        for comp, entry in sorted(self.components.items()):
            missing = sorted(set(entry.patterns) - set(names))
            if missing:
                raise ValueError(
                    f"intent: component '{comp}' lists patterns {missing} that are not defined in `patterns`"
                )
        return self


def load_intent(source: "str | Path | dict[str, Any] | Intent | None") -> Intent | None:
    """Accept a path to a JSON file, a dict, an Intent, or None. Bad content raises."""
    if source is None:
        return None
    if isinstance(source, Intent):
        return source
    if isinstance(source, dict):
        return Intent.model_validate(source)
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError(f"intent file not found: {path}")
    return Intent.model_validate(json.loads(path.read_text(encoding="utf-8")))


def fingerprint(members: list[tuple[str, list[str]]]) -> str:
    """12-hex digest of (module name, public symbols) pairs. Changes on structural edits only."""
    lines = sorted(f"{name}:{','.join(sorted(symbols))}" for name, symbols in members)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:12]
